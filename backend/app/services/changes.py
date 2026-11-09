"""变更计划、审批、模拟执行、回读验证。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings, settings as default_settings
from app.core.errors import AppError
from app.models.entities import ApprovalRecord, ChangePlanRecord
from app.services.audit import AuditService
from app.services.providers.mock import MockProviderSet

ACTION_LEVELS = {
    "isolate_port": "change_high",
    "restart_service": "change_low",
    "restart_host": "change_high",
    "power_off": "change_high",
    "config_change": "change_high",
    "batch_change": "forbidden",
}
FORBIDDEN = {
    ("core-sw-01", "power_off"),
    ("db-prod-01", "restart_host"),
    ("db-prod-01", "power_off"),
    ("*", "batch_change"),
}


def canonical_plan(asset_id: str, action: str, params: dict, window_start: str | None,
                   window_end: str | None) -> tuple[str, str]:
    payload = {
        "asset_id": asset_id,
        "action": action,
        "params": params or {},
        "window_start": window_start or "",
        "window_end": window_end or "",
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return canonical, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PolicyService:
    def __init__(self, settings: Settings = default_settings) -> None:
        self.settings = settings

    def evaluate(self, asset, action: str) -> dict:
        level = ACTION_LEVELS.get(action)
        if level is None:
            return {"decision": "deny", "level": "unknown", "reason": f"未知动作：{action}"}
        if level == "forbidden" or (asset.id, action) in FORBIDDEN or ("*", action) in FORBIDDEN:
            return {"decision": "deny", "level": level, "reason": "该动作在禁止清单中"}
        if asset.no_touch:
            return {"decision": "deny", "level": level, "reason": "资产标记为不可触碰"}
        if level not in asset.allowed_actions:
            return {"decision": "deny", "level": level, "reason": f"资产未授权 {level} 动作"}
        if self.settings.read_only_mode or self.settings.policy_mode == "read_only":
            return {"decision": "deny", "level": level, "reason": "当前处于只读模式"}
        if level in ("change_low", "change_high"):
            return {"decision": "ask", "level": level, "reason": "需要人工审批"}
        return {"decision": "allow", "level": level, "reason": "只读/检查动作"}


class MockChangeProvider:
    """模拟执行器：不碰真实设备，结果明确标 simulated。"""

    def dry_run(self, asset, action: str, params: dict) -> dict:
        if action == "isolate_port" and not params.get("port"):
            return {"ok": False, "summary": "缺少端口参数 port"}
        if action == "restart_service" and not params.get("service"):
            return {"ok": False, "summary": "缺少服务名参数 service"}
        return {"ok": True, "summary": f"dry-run 通过（模拟）：{asset.id} {action} {params}"}

    def execute(self, asset, action: str, params: dict) -> dict:
        if action == "isolate_port":
            summary = f"已隔离 {asset.id} 端口 {params.get('port')}，业务按预案切至备用链路（模拟）"
        elif action == "restart_service":
            summary = f"已重启 {asset.id} 服务 {params.get('service')}（模拟）"
        elif action == "restart_host":
            summary = f"已重启主机 {asset.id}（模拟）"
        else:
            summary = f"已执行 {asset.id} {action}（模拟）"
        return {"status": "succeeded", "summary": summary, "simulated": True,
                "executed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    def verify(self, asset, action: str, params: dict) -> dict:
        if action == "isolate_port":
            checks = [
                f"{params.get('port')} 状态 down",
                "备用链路流量正常",
                "ALM-1001/1002/1003 转 cleared（模拟）",
            ]
        elif action == "restart_service":
            checks = [f"{params.get('service')} 进程已启动", "健康检查通过", "错误率恢复正常（模拟）"]
        else:
            checks = ["设备状态已回读（模拟）"]
        return {"status": "succeeded", "summary": "回读验证通过（模拟）", "checks": checks, "simulated": True}


class ChangeService:
    def __init__(self, providers: MockProviderSet, audit: AuditService,
                 policy: PolicyService | None = None, provider: MockChangeProvider | None = None,
                 settings: Settings = default_settings) -> None:
        self.providers = providers
        self.audit = audit
        self.policy = policy or PolicyService(settings)
        self.provider = provider or MockChangeProvider()
        self.settings = settings

    def _asset(self, query: str):
        asset, candidates = self.providers.resolve_asset(query)
        if not asset or candidates:
            raise AppError("ASSET_NOT_FOUND", f"找不到唯一资产：{query}", 404)
        return asset

    def propose(self, db: Session, session_id: str, asset_query: str, action: str, params: dict,
                reason: str, impact: str, rollback: str,
                window_start: str | None = None, window_end: str | None = None) -> dict:
        asset = self._asset(asset_query)
        if not rollback.strip():
            raise AppError("ROLLBACK_REQUIRED", "变更计划必须写回滚方式", 400)
        decision = self.policy.evaluate(asset, action)
        if decision["decision"] == "deny":
            self.audit.append(db, session_id=session_id, actor="local", action="change.denied",
                              target_type="asset", target_id=asset.id, params=params,
                              result="denied", error=decision["reason"])
            raise AppError("POLICY_DENIED", decision["reason"], 403)
        dry = self.provider.dry_run(asset, action, params)
        if not dry.get("ok"):
            raise AppError("DRY_RUN_FAILED", dry.get("summary", "dry-run 失败"), 400)
        _, plan_hash = canonical_plan(asset.id, action, params, window_start, window_end)
        now = datetime.utcnow()
        plan = ChangePlanRecord(
            id=f"chg-{uuid4().hex[:12]}", session_id=session_id, owner_id="local",
            asset_id=asset.id, action=action,
            params_json=json.dumps(params or {}, ensure_ascii=False),
            reason=reason, impact=impact, rollback=rollback,
            window_start=window_start, window_end=window_end,
            plan_hash=plan_hash, status="pending_approval",
            dry_run_json=json.dumps(dry, ensure_ascii=False),
            created_at=now, updated_at=now,
        )
        db.add(plan)
        db.commit()
        self.audit.append(db, session_id=session_id, actor="local", action="change.proposed",
                          target_type="asset", target_id=asset.id, params=params,
                          plan_hash=plan_hash, result="ok")
        return self.to_dict(plan)

    def approve(self, db: Session, plan_id: str, comment: str = "") -> dict:
        plan = db.get(ChangePlanRecord, plan_id)
        if not plan or plan.owner_id != "local":
            raise AppError("PLAN_NOT_FOUND", "变更计划不存在", 404)
        if plan.status != "pending_approval":
            raise AppError("PLAN_NOT_PENDING", f"计划当前状态 {plan.status}，不能批准", 409)
        now = datetime.utcnow()
        approval = ApprovalRecord(
            id=f"apr-{uuid4().hex[:12]}", plan_id=plan.id, plan_hash=plan.plan_hash,
            approved_by="local", approved_at=now,
            expires_at=now + timedelta(minutes=self.settings.approval_ttl_minutes),
            comment=comment,
        )
        plan.status = "approved"
        plan.updated_at = now
        db.add(approval)
        db.commit()
        self.audit.append(db, session_id=plan.session_id, actor="local", action="change.approved",
                          target_type="plan", target_id=plan.id, params={"comment": comment},
                          plan_hash=plan.plan_hash, approval_id=approval.id, result="ok")
        return {"approval_id": approval.id, "expires_at": approval.expires_at.strftime("%Y-%m-%d %H:%M:%S"),
                "plan": self.to_dict(plan)}

    def reject(self, db: Session, plan_id: str, reason: str = "") -> dict:
        plan = db.get(ChangePlanRecord, plan_id)
        if not plan or plan.owner_id != "local":
            raise AppError("PLAN_NOT_FOUND", "变更计划不存在", 404)
        plan.status = "rejected"
        plan.updated_at = datetime.utcnow()
        db.commit()
        self.audit.append(db, session_id=plan.session_id, actor="local", action="change.rejected",
                          target_type="plan", target_id=plan.id, params={"reason": reason},
                          plan_hash=plan.plan_hash, result="rejected")
        return self.to_dict(plan)

    def execute(self, db: Session, plan_id: str) -> dict:
        plan = db.get(ChangePlanRecord, plan_id)
        if not plan or plan.owner_id != "local":
            raise AppError("PLAN_NOT_FOUND", "变更计划不存在", 404)
        if plan.status != "approved":
            self.audit.append(db, session_id=plan.session_id, actor="local", action="change.denied",
                              target_type="plan", target_id=plan.id, params={},
                              plan_hash=plan.plan_hash, result="denied", error="计划未批准")
            raise AppError("APPROVAL_REQUIRED", "没有有效审批，拒绝执行", 403)
        approval = (db.query(ApprovalRecord)
                    .filter(ApprovalRecord.plan_id == plan.id, ApprovalRecord.used_at.is_(None))
                    .order_by(ApprovalRecord.approved_at.desc()).first())
        now = datetime.utcnow()
        if not approval or approval.expires_at < now:
            self.audit.append(db, session_id=plan.session_id, actor="local", action="change.denied",
                              target_type="plan", target_id=plan.id, params={},
                              plan_hash=plan.plan_hash, result="denied", error="审批不存在或已过期")
            raise AppError("APPROVAL_EXPIRED", "审批不存在或已过期，拒绝执行", 403)
        _, current_hash = canonical_plan(plan.asset_id, plan.action, json.loads(plan.params_json or "{}"),
                                         plan.window_start, plan.window_end)
        if approval.plan_hash != plan.plan_hash or current_hash != plan.plan_hash:
            self.audit.append(db, session_id=plan.session_id, actor="local", action="change.denied",
                              target_type="plan", target_id=plan.id, params={},
                              plan_hash=plan.plan_hash, approval_id=approval.id,
                              result="denied", error="plan_hash 不一致")
            raise AppError("PLAN_HASH_MISMATCH", "审批与计划不一致，拒绝执行", 403)
        asset = self.providers.get_asset(plan.asset_id)
        if not asset:
            raise AppError("ASSET_NOT_FOUND", "资产不存在", 404)
        dry = self.provider.dry_run(asset, plan.action, json.loads(plan.params_json or "{}"))
        if not dry.get("ok"):
            plan.status = "failed"
            db.commit()
            raise AppError("DRY_RUN_FAILED", dry.get("summary", "dry-run 失败"), 400)
        try:
            self.audit.append(db, session_id=plan.session_id, actor="local", action="change.executing",
                              target_type="plan", target_id=plan.id, params={},
                              plan_hash=plan.plan_hash, approval_id=approval.id, result="ok")
        except Exception as exc:  # noqa: BLE001
            raise AppError("AUDIT_WRITE_FAILED", "审计写入失败，执行中止", 503) from exc
        plan.status = "executing"
        plan.updated_at = now
        db.commit()
        result = self.provider.execute(asset, plan.action, json.loads(plan.params_json or "{}"))
        plan.status = "succeeded"
        plan.execution_json = json.dumps(result, ensure_ascii=False)
        plan.updated_at = datetime.utcnow()
        approval.used_at = datetime.utcnow()
        db.commit()
        try:
            self.audit.append(db, session_id=plan.session_id, actor="local", action="change.executed",
                              target_type="plan", target_id=plan.id, params={},
                              plan_hash=plan.plan_hash, approval_id=approval.id, result="ok")
        except Exception as exc:  # noqa: BLE001
            plan.status = "unknown"
            db.commit()
            raise AppError("AUDIT_WRITE_FAILED", "执行结果审计写入失败，状态未知", 503) from exc
        return self.to_dict(plan)

    def verify(self, db: Session, plan_id: str) -> dict:
        plan = db.get(ChangePlanRecord, plan_id)
        if not plan or plan.owner_id != "local":
            raise AppError("PLAN_NOT_FOUND", "变更计划不存在", 404)
        if plan.status != "succeeded":
            raise AppError("PLAN_NOT_EXECUTED", f"计划当前状态 {plan.status}，不能回读", 409)
        asset = self.providers.get_asset(plan.asset_id)
        if not asset:
            raise AppError("ASSET_NOT_FOUND", "资产不存在", 404)
        result = self.provider.verify(asset, plan.action, json.loads(plan.params_json or "{}"))
        plan.status = "verified" if result.get("status") == "succeeded" else "failed"
        plan.verification_json = json.dumps(result, ensure_ascii=False)
        plan.updated_at = datetime.utcnow()
        db.commit()
        self.audit.append(db, session_id=plan.session_id, actor="local", action="change.verified",
                          target_type="plan", target_id=plan.id, params={},
                          plan_hash=plan.plan_hash, result=plan.status)
        return self.to_dict(plan)

    def get(self, db: Session, plan_id: str) -> dict:
        plan = db.get(ChangePlanRecord, plan_id)
        if not plan or plan.owner_id != "local":
            raise AppError("PLAN_NOT_FOUND", "变更计划不存在", 404)
        return self.to_dict(plan)

    def to_dict(self, plan: ChangePlanRecord) -> dict:
        return {
            "plan_id": plan.id,
            "session_id": plan.session_id,
            "asset_id": plan.asset_id,
            "action": plan.action,
            "params": json.loads(plan.params_json or "{}"),
            "reason": plan.reason,
            "impact": plan.impact,
            "rollback": plan.rollback,
            "window_start": plan.window_start,
            "window_end": plan.window_end,
            "plan_hash": plan.plan_hash,
            "status": plan.status,
            "dry_run": json.loads(plan.dry_run_json) if plan.dry_run_json else None,
            "execution": json.loads(plan.execution_json) if plan.execution_json else None,
            "verification": json.loads(plan.verification_json) if plan.verification_json else None,
            "created_at": plan.created_at.strftime("%Y-%m-%d %H:%M:%S") if plan.created_at else "",
        }
