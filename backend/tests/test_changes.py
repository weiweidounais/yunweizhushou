from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.errors import AppError
from app.models.entities import ApprovalRecord, AuditLogRecord, SessionRecord
from app.services.audit import AuditService
from app.services.changes import ChangeService
from app.services.providers.mock import MockProviderSet


def make_service():
    db: Session = SessionLocal()
    db.add(SessionRecord(id="s-changes", owner_id="local", title="变更测试"))
    db.commit()
    audit = AuditService()
    service = ChangeService(MockProviderSet(), audit,
                            settings=replace(settings, read_only_mode=False, policy_mode="approval"))
    return db, service, audit


def propose(service, db, action="isolate_port", params=None):
    return service.propose(db, "s-changes", "core-sw-01", action, params or {"port": "Gi1/0/24"},
                           "光模块劣化，需要隔离端口", "该口业务瞬断", "确认备用链路后回切")


def test_propose_creates_pending_plan_and_audit():
    db, service, audit = make_service()
    plan = propose(service, db)
    assert plan["status"] == "pending_approval"
    assert plan["plan_hash"]
    assert plan["params"]["port"] == "Gi1/0/24"
    chain = audit.verify_chain(db)
    assert chain["valid"] is True and chain["checked"] >= 1


def test_forbidden_action_denied_and_audited():
    db, service, audit = make_service()
    with pytest.raises(AppError) as exc:
        service.propose(db, "s-changes", "core-sw-01", "power_off", {},
                        "测试禁止动作", "", "回滚")
    assert exc.value.code == "POLICY_DENIED"
    records = audit.list(db, 10)
    assert any(r["action"] == "change.denied" for r in records)


def test_execute_without_approval_denied():
    db, service, audit = make_service()
    plan = propose(service, db)
    with pytest.raises(AppError) as exc:
        service.execute(db, plan["plan_id"])
    assert exc.value.code == "APPROVAL_REQUIRED"
    refreshed = service.get(db, plan["plan_id"])
    assert refreshed["status"] == "pending_approval"


def test_approve_execute_verify_and_audit_chain():
    db, service, audit = make_service()
    plan = propose(service, db)
    approved = service.approve(db, plan["plan_id"], "演示批准")
    assert approved["approval_id"].startswith("apr-")
    executed = service.execute(db, plan["plan_id"])
    assert executed["status"] == "succeeded"
    assert executed["execution"]["simulated"] is True
    verified = service.verify(db, plan["plan_id"])
    assert verified["status"] == "verified"
    assert verified["verification"]["status"] == "succeeded"
    approval = db.get(ApprovalRecord, approved["approval_id"])
    assert approval.used_at is not None
    chain = audit.verify_chain(db)
    assert chain["valid"] is True
    actions = {r["action"] for r in audit.list(db, 20)}
    assert {"change.proposed", "change.approved", "change.executed", "change.verified"} <= actions


def test_expired_approval_denied():
    db, service, _ = make_service()
    plan = propose(service, db)
    approved = service.approve(db, plan["plan_id"])
    approval = db.get(ApprovalRecord, approved["approval_id"])
    approval.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    with pytest.raises(AppError) as exc:
        service.execute(db, plan["plan_id"])
    assert exc.value.code == "APPROVAL_EXPIRED"


def test_plan_hash_mismatch_denied():
    db, service, _ = make_service()
    plan = propose(service, db)
    service.approve(db, plan["plan_id"])
    from app.models.entities import ChangePlanRecord
    row = db.get(ChangePlanRecord, plan["plan_id"])
    row.params_json = json.dumps({"port": "Gi1/0/99"})
    db.commit()
    with pytest.raises(AppError) as exc:
        service.execute(db, plan["plan_id"])
    assert exc.value.code == "PLAN_HASH_MISMATCH"


def test_audit_write_failure_blocks_execute(monkeypatch):
    db, service, audit = make_service()
    plan = propose(service, db)
    service.approve(db, plan["plan_id"])
    def boom(*args, **kwargs):
        raise RuntimeError("disk full")
    monkeypatch.setattr(audit, "append", boom)
    with pytest.raises(AppError) as exc:
        service.execute(db, plan["plan_id"])
    assert exc.value.code == "AUDIT_WRITE_FAILED"
    refreshed = service.get(db, plan["plan_id"])
    assert refreshed["status"] == "approved"


def test_audit_chain_detects_tamper():
    db, service, audit = make_service()
    plan = propose(service, db)
    service.approve(db, plan["plan_id"], "ok")
    assert audit.verify_chain(db)["valid"] is True
    row = db.query(AuditLogRecord).order_by(AuditLogRecord.id.desc()).first()
    row.hash = "0" * 64
    db.commit()
    assert audit.verify_chain(db)["valid"] is False


def test_approval_message_executes_deterministically():
    from app.core.db import SessionLocal
    from app.models.entities import SessionRecord
    from tests.conftest import make_client

    client, llm = make_client([])
    app = client.app
    db = SessionLocal()
    db.add(SessionRecord(id="s-approval-chat", owner_id="local", title="审批执行"))
    db.commit()
    svc = ChangeService(app.state.providers, AuditService(),
                        settings=replace(settings, read_only_mode=False, policy_mode="approval"))
    plan = svc.propose(db, "s-approval-chat", "core-sw-01", "isolate_port",
                       {"port": "Gi1/0/24"}, "光模块劣化", "业务瞬断", "确认备用链路后回切")
    svc.approve(db, plan["plan_id"])
    r = client.post("/api/sessions/s-approval-chat/chat",
                    json={"message": f"已批准 plan_id={plan['plan_id']}，请执行并回读验证。"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["change_plan"]["status"] == "verified"
    assert [t["name"] for t in data["tool_calls"]] == ["execute_change", "verify_change"]
    assert len(llm.calls) == 0


def test_session_list_and_latest_change_plan():
    from app.core.db import SessionLocal
    from app.models.entities import SessionRecord
    from tests.conftest import make_client

    client, _ = make_client([])
    created = client.post("/api/sessions", json={"title": "历史会话"}).json()
    listing = client.get("/api/sessions?limit=10")
    assert listing.status_code == 200
    ids = [s["id"] for s in listing.json()["sessions"]]
    assert created["id"] in ids

    app = client.app
    db = SessionLocal()
    db.add(SessionRecord(id="s-latest-plan", owner_id="local", title="带计划"))
    db.commit()
    svc = ChangeService(app.state.providers, AuditService(),
                        settings=replace(settings, read_only_mode=False, policy_mode="approval"))
    plan = svc.propose(db, "s-latest-plan", "core-sw-01", "isolate_port",
                       {"port": "Gi1/0/24"}, "光模块劣化", "业务瞬断", "no shutdown 恢复")
    detail = client.get("/api/sessions/s-latest-plan")
    assert detail.status_code == 200
    assert detail.json()["latest_change_plan"]["plan_id"] == plan["plan_id"]
