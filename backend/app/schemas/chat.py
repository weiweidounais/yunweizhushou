"""API 与会话结构；Assessment 同时用于模型交卷校验。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Hypothesis(BaseModel):
    cause: str = Field(min_length=1, max_length=120)
    confidence: Literal["high", "medium", "low"] = "medium"
    evidence: list[str] = Field(default_factory=list, max_length=3)
    falsification: str = Field(default="", max_length=160)


class Recommendation(BaseModel):
    step: str = Field(min_length=1, max_length=160)
    risk: Literal["low", "medium", "high"] = "medium"
    requires_change: bool = False
    rollback: str = Field(default="", max_length=160)


class Assessment(BaseModel):
    summary: str = Field(min_length=1, max_length=400)
    impact: str = Field(default="", max_length=200)
    hypotheses: list[Hypothesis] = Field(min_length=1, max_length=3)
    recommendations: list[Recommendation] = Field(min_length=1, max_length=4)
    unknowns: list[str] = Field(default_factory=list, max_length=3)

    @model_validator(mode="before")
    @classmethod
    def _trim_for_brevity(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)
        data["summary"] = str(data.get("summary", ""))[:400]
        data["impact"] = str(data.get("impact", ""))[:200]
        data["hypotheses"] = list(data.get("hypotheses") or [])[:3]
        data["recommendations"] = list(data.get("recommendations") or [])[:4]
        data["unknowns"] = [str(x)[:160] for x in (data.get("unknowns") or [])[:3]]
        for h in data["hypotheses"]:
            if isinstance(h, dict):
                h["cause"] = str(h.get("cause", ""))[:120]
                h["evidence"] = [str(e)[:180] for e in (h.get("evidence") or [])[:3]]
                h["falsification"] = str(h.get("falsification", ""))[:160]
        for r in data["recommendations"]:
            if isinstance(r, dict):
                r["step"] = str(r.get("step", ""))[:160]
                r["rollback"] = str(r.get("rollback", ""))[:160]
        return data

    @model_validator(mode="after")
    def _evidence_and_rollback(self) -> "Assessment":
        for h in self.hypotheses:
            if not any(e.strip() for e in h.evidence) and "推测" not in h.cause:
                raise ValueError("每条假设至少一条 evidence，或在 cause 中写明「推测」")
        for r in self.recommendations:
            if r.requires_change and not r.rollback.strip():
                raise ValueError("requires_change=true 的建议必须写 rollback")
        return self


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class SessionCreate(BaseModel):
    title: str = Field(default="新会话", max_length=100)


class ToolCallView(BaseModel):
    name: str
    args: dict
    result_preview: str
    status: str
    duration_ms: int


class Usage(BaseModel):
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    request_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    assessment: Assessment | None = None
    tool_calls: list[ToolCallView] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: int = 0
    change_plan: dict | None = None


class MessageView(BaseModel):
    id: int
    role: str
    content: str
    assessment: Assessment | None = None
    created_at: datetime


class SessionSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class SessionView(BaseModel):
    id: str
    title: str
    messages: list[MessageView]
    created_at: datetime
    latest_change_plan: dict | None = None


class HealthView(BaseModel):
    status: str
    model_configured: bool
    read_only: bool
    model: str
