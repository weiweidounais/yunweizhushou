"""审计：只追加、哈希链；任何变更、审批、拒绝、执行、回读都要留痕。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.entities import AuditLogRecord

GENESIS = "0" * 64


def _ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def _display_ts(value: datetime) -> str:
    """库里存 UTC（SQLite 读出来是 naive），展示转本地时区。"""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _digest_params(params: dict | None) -> str:
    payload = json.dumps(params or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class AuditService:
    def append(self, db: Session, *, session_id: str, actor: str, action: str,
               target_type: str = "", target_id: str = "", params: dict | None = None,
               plan_hash: str = "", approval_id: str = "", result: str = "ok",
               error: str = "") -> AuditLogRecord:
        last = db.query(AuditLogRecord).order_by(AuditLogRecord.id.desc()).first()
        prev = last.hash if last else GENESIS
        now = datetime.now(timezone.utc)
        record = {
            "ts": _ts(now),
            "session_id": session_id,
            "actor": actor,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "params_digest": _digest_params(params),
            "plan_hash": plan_hash,
            "approval_id": approval_id,
            "result": result,
            "error": error,
        }
        canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        row = AuditLogRecord(
            ts=now, session_id=session_id, actor=actor, action=action,
            target_type=target_type, target_id=target_id,
            params_digest=record["params_digest"], plan_hash=plan_hash,
            approval_id=approval_id, result=result, error=error,
            prev_hash=prev, hash=hashlib.sha256((prev + canonical).encode("utf-8")).hexdigest(),
        )
        db.add(row)
        db.commit()
        return row

    def _canonical(self, row: AuditLogRecord) -> str:
        record = {
            "ts": _ts(row.ts),
            "session_id": row.session_id,
            "actor": row.actor,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "params_digest": row.params_digest,
            "plan_hash": row.plan_hash,
            "approval_id": row.approval_id,
            "result": row.result,
            "error": row.error,
        }
        return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def verify_chain(self, db: Session) -> dict:
        rows = db.query(AuditLogRecord).order_by(AuditLogRecord.id.asc()).all()
        prev = GENESIS
        for row in rows:
            expected = hashlib.sha256((prev + self._canonical(row)).encode("utf-8")).hexdigest()
            if row.prev_hash != prev or row.hash != expected:
                return {"valid": False, "checked": len(rows), "broken_at": row.id}
            prev = row.hash
        return {"valid": True, "checked": len(rows), "broken_at": None}

    def list(self, db: Session, limit: int = 50) -> list[dict]:
        rows = (db.query(AuditLogRecord).order_by(AuditLogRecord.id.desc()).limit(max(1, min(limit, 200))).all())
        return [{
            "id": r.id,
            "ts": _display_ts(r.ts),
            "session_id": r.session_id,
            "actor": r.actor,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "params_digest": r.params_digest,
            "plan_hash": r.plan_hash,
            "approval_id": r.approval_id,
            "result": r.result,
            "error": r.error,
            "hash": r.hash[:16] + "…",
        } for r in rows]
