"""API 路由：健康、会话、聊天、示例问题。"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import AppError
from app.models.entities import ChangePlanRecord, MessageRecord, SessionRecord
from app.schemas.chat import (Assessment, ChatRequest, ChatResponse, HealthView, MessageView,
                              SessionCreate, SessionSummary, SessionView, ToolCallView)
from pydantic import BaseModel, Field
from app.services.agent import AgentService

router = APIRouter(prefix="/api")


def _agent(request: Request) -> AgentService:
    return request.app.state.agent


def _session_or_404(db: Session, session_id: str) -> SessionRecord:
    row = db.get(SessionRecord, session_id)
    if row is None or row.owner_id != "local":
        raise AppError("SESSION_NOT_FOUND", "会话不存在", 404)
    return row


def _message_view(row: MessageRecord) -> MessageView:
    assessment = None
    if row.assessment_json:
        try:
            assessment = Assessment.model_validate_json(row.assessment_json)
        except Exception:  # noqa: BLE001 - 旧数据损坏时不让整页失败
            assessment = None
    return MessageView(id=row.id, role=row.role, content=row.content,
                       assessment=assessment, created_at=row.created_at)


@router.get("/health", response_model=HealthView)
def health(request: Request) -> HealthView:
    s = request.app.state.settings
    return HealthView(status="ok", model_configured=s.model_configured,
                      read_only=s.read_only_mode, model=s.model_name)


@router.post("/sessions")
def create_session(payload: SessionCreate, db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc)
    row = SessionRecord(id=uuid4().hex, owner_id="local", title=payload.title or "新会话",
                        created_at=now, updated_at=now)
    db.add(row)
    db.commit()
    return {"id": row.id, "title": row.title}


@router.get("/sessions")
def list_sessions(limit: int = 20, db: Session = Depends(get_db)) -> dict:
    limit = max(1, min(limit, 50))
    rows = (db.query(SessionRecord).filter(SessionRecord.owner_id == "local")
            .order_by(SessionRecord.updated_at.desc()).limit(limit).all())
    sessions = []
    for row in rows:
        count = db.query(MessageRecord).filter(MessageRecord.session_id == row.id).count()
        sessions.append(SessionSummary(id=row.id, title=row.title, created_at=row.created_at,
                                       updated_at=row.updated_at, message_count=count))
    return {"sessions": [s.model_dump(mode="json") for s in sessions]}


@router.get("/sessions/{session_id}", response_model=SessionView)
def get_session(session_id: str, request: Request, db: Session = Depends(get_db)) -> SessionView:
    row = _session_or_404(db, session_id)
    messages = (db.query(MessageRecord).filter(MessageRecord.session_id == session_id)
                .order_by(MessageRecord.id.asc()).all())
    latest = (db.query(ChangePlanRecord).filter(ChangePlanRecord.session_id == session_id)
              .order_by(ChangePlanRecord.created_at.desc()).first())
    latest_plan = request.app.state.changes.to_dict(latest) if latest else None
    return SessionView(id=row.id, title=row.title, created_at=row.created_at,
                       messages=[_message_view(m) for m in messages],
                       latest_change_plan=latest_plan)


@router.post("/sessions/{session_id}/chat", response_model=ChatResponse)
def chat(session_id: str, payload: ChatRequest, request: Request,
         db: Session = Depends(get_db)) -> ChatResponse:
    session = _session_or_404(db, session_id)
    agent = _agent(request)
    history = agent.history(db, session_id)

    user_message = MessageRecord(session_id=session_id, role="user", content=payload.message)
    db.add(user_message)
    session.updated_at = datetime.now(timezone.utc)
    if session.title in ("新会话", "") and payload.message.strip():
        session.title = payload.message.strip().splitlines()[0][:40]
    db.commit()

    started = time.monotonic()
    result = agent.run(db, session_id, payload.message, history=history)
    elapsed_ms = int((time.monotonic() - started) * 1000)

    assistant = MessageRecord(
        session_id=session_id,
        role="assistant",
        content=result.reply,
        assessment_json=result.assessment.model_dump_json() if result.assessment else None,
    )
    db.add(assistant)
    session.updated_at = datetime.now(timezone.utc)
    db.commit()

    return ChatResponse(
        session_id=session_id,
        reply=result.reply,
        assessment=result.assessment,
        tool_calls=[ToolCallView(**c) for c in result.tool_calls],
        usage=result.usage,
        warnings=result.warnings,
        elapsed_ms=elapsed_ms,
        change_plan=result.change_plan,
    )


@router.get("/demo/cases")
def demo_cases(request: Request) -> dict:
    data_file = request.app.state.providers.data_dir / "eval_cases.json"
    try:
        cases = json.loads(data_file.read_text(encoding="utf-8"))["cases"]
    except (OSError, ValueError):
        cases = []
    return {"cases": [{"id": c["id"], "question": c["question"], "asset_id": c["asset_id"]}
                      for c in cases[:3]]}


class ApprovalRequest(BaseModel):
    comment: str = Field(default="", max_length=300)


class RejectRequest(BaseModel):
    reason: str = Field(default="", max_length=300)


@router.post("/changes/{plan_id}/approve")
def approve_change(plan_id: str, payload: ApprovalRequest, request: Request,
                   db: Session = Depends(get_db)) -> dict:
    return request.app.state.changes.approve(db, plan_id, payload.comment)


@router.post("/changes/{plan_id}/reject")
def reject_change(plan_id: str, payload: RejectRequest, request: Request,
                  db: Session = Depends(get_db)) -> dict:
    return {"plan": request.app.state.changes.reject(db, plan_id, payload.reason)}


@router.get("/changes/{plan_id}")
def get_change(plan_id: str, request: Request, db: Session = Depends(get_db)) -> dict:
    return request.app.state.changes.get(db, plan_id)


@router.get("/audit")
def list_audit(request: Request, limit: int = 50, db: Session = Depends(get_db)) -> dict:
    audit = request.app.state.audit
    return {"records": audit.list(db, limit=limit), "chain": audit.verify_chain(db)}


@router.get("/audit/verify")
def verify_audit(request: Request, db: Session = Depends(get_db)) -> dict:
    return request.app.state.audit.verify_chain(db)
