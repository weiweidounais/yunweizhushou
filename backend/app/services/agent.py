"""Agent 循环：模型 → 工具 → 结果 → 模型，直到 submit_assessment 交卷。

演示阶段默认开启 fast_mode：服务端先预取一次 get_incident_context，把压缩后的上下文直接给模型，
模型通常只需一次 submit_assessment 交卷，减少等待；没有识别到资产时退回普通工具循环。
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, settings as default_settings
from app.core.errors import AppError
from app.models.entities import LLMUsageRecord, MessageRecord, ToolCallRecord
from app.schemas.chat import Assessment, Usage
from app.services.changes import ChangeService
from app.services.llm import LLMClient
from app.services.providers.mock import MockProviderSet
from app.services.tools.registry import ToolContext, ToolRegistry, build_registry

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system.md"
MAX_TOOL_RESULT_CHARS = 6000
HISTORY_MESSAGES = 6
MAX_SUBMIT_REJECTS = 2
MAX_OUTPUT_TOKENS = 1600
CHANGE_WORDS = ("变更", "隔离", "重启", "下电", "改配置", "执行", "批准", "审批", "回滚")
APPROVAL_RE = re.compile(r"已批准\s*plan_id=(chg-[0-9a-f]+)")


@dataclass
class AgentResult:
    reply: str
    assessment: Assessment | None = None
    tool_calls: list[dict] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    warnings: list[str] = field(default_factory=list)
    change_plan: dict | None = None


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _clip(text: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n……（结果过长，已截断；原文共 {len(text)} 字）"


def _text_of(blocks: list[dict]) -> str:
    return "".join(str(b.get("text", "")) for b in blocks if b.get("type") == "text")


def _merge_roles(messages: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for m in messages:
        if merged and merged[-1]["role"] == m["role"] and isinstance(merged[-1]["content"], str) and isinstance(m["content"], str):
            merged[-1]["content"] = merged[-1]["content"] + "\n\n" + m["content"]
        else:
            merged.append(dict(m))
    return merged


def _compact_incident(data: dict) -> dict:
    """把一次上下文压缩到模型够用、又不拖慢响应的程度。"""
    asset = data.get("asset") or {}
    keep = ["id", "name", "type", "env", "criticality", "owner", "allowed_actions"]
    alarms = []
    for a in (data.get("active_alarms") or [])[:5]:
        alarms.append({k: a.get(k) for k in ["id", "name", "severity", "description", "first_seen"]})
    metrics = {}
    for name, m in ((data.get("metrics") or {}).get("metrics") or {}).items():
        metrics[name] = {
            "unit": m.get("unit"),
            "normal": m.get("normal"),
            "points": (m.get("points") or [])[-3:],
        }
    runbooks = []
    for rb in (data.get("runbooks") or [])[:2]:
        runbooks.append({
            "id": rb.get("id"), "title": rb.get("title"), "risk": rb.get("risk"),
            "requires_change": rb.get("requires_change"),
            "snippet": (rb.get("snippet") or "")[:180],
        })
    return {
        "asset": {k: asset.get(k) for k in keep},
        "active_alarms": alarms,
        "metrics": metrics,
        "topology": (data.get("topology") or [])[:4],
        "runbooks": runbooks,
    }


class AgentService:
    def __init__(self, llm: LLMClient, providers: MockProviderSet,
                 settings: Settings = default_settings, registry: ToolRegistry | None = None,
                 change_service: ChangeService | None = None) -> None:
        self.llm = llm
        self.providers = providers
        self.settings = settings
        self.registry = registry or build_registry()
        self.change_service = change_service
        self.system = load_system_prompt()

    def history(self, db: Session, session_id: str) -> list[dict]:
        rows = (db.query(MessageRecord)
                .filter(MessageRecord.session_id == session_id)
                .order_by(MessageRecord.id.desc())
                .limit(HISTORY_MESSAGES)
                .all())
        rows.reverse()
        out = []
        for row in rows:
            if row.role not in ("user", "assistant"):
                continue
            content = row.content or ""
            if not content and row.assessment_json:
                try:
                    content = json.loads(row.assessment_json).get("summary", "")
                except ValueError:
                    content = ""
            if content:
                out.append({"role": row.role, "content": content})
        return _merge_roles(out)

    def _prefetch(self, user_message: str, ctx: ToolContext):
        """识别用户问题里的资产，先拉一次上下文。返回 (压缩上下文, 工具卡片) 或 None。"""
        if not self.settings.fast_mode:
            return None
        if any(w in user_message for w in CHANGE_WORDS):
            return None
        asset, candidates = self.providers.resolve_asset(user_message)
        if not asset or candidates:
            return None
        result_text, status = self.registry.execute(
            "get_incident_context", {"asset": asset.id, "window_hours": 24}, ctx)
        if status != "ok":
            return None
        try:
            data = json.loads(result_text)
        except ValueError:
            return None
        compact = json.dumps(_compact_incident(data), ensure_ascii=False)
        preview = compact[:400] + ("…" if len(compact) > 400 else "")
        return compact, {
            "name": "get_incident_context",
            "args": {"asset": asset.id, "window_hours": 24},
            "result_preview": preview,
            "status": "ok",
            "duration_ms": 0,
        }

    def _execute_approved(self, db: Session, session_id: str, plan_id: str) -> AgentResult:
        """审批后的执行/回读由确定性代码完成，不让模型重新提议或绕过审批。"""
        if self.change_service is None:
            raise AppError("CHANGE_SERVICE_MISSING", "变更服务未初始化", 503)
        executed = self.change_service.execute(db, plan_id)
        verified = self.change_service.verify(db, plan_id)
        calls = [
            {"name": "execute_change", "args": {"plan_id": plan_id},
             "result_preview": json.dumps(executed.get("execution") or {}, ensure_ascii=False)[:400],
             "status": "ok", "duration_ms": 0},
            {"name": "verify_change", "args": {"plan_id": plan_id},
             "result_preview": json.dumps(verified.get("verification") or {}, ensure_ascii=False)[:400],
             "status": "ok", "duration_ms": 0},
        ]
        db.add(ToolCallRecord(session_id=session_id, name="execute_change",
                              args_json=json.dumps({"plan_id": plan_id}, ensure_ascii=False),
                              result_text=calls[0]["result_preview"], status="ok", duration_ms=0))
        db.add(ToolCallRecord(session_id=session_id, name="verify_change",
                              args_json=json.dumps({"plan_id": plan_id}, ensure_ascii=False),
                              result_text=calls[1]["result_preview"], status="ok", duration_ms=0))
        db.commit()
        reply = "已按批准执行并回读验证："
        reply += (verified.get("execution") or {}).get("summary", "")
        reply += "；" + (verified.get("verification") or {}).get("summary", "")
        return AgentResult(reply=reply, tool_calls=calls, change_plan=verified,
                           usage=Usage(), warnings=[])

    def run(self, db: Session, session_id: str, user_message: str,
            history: list[dict] | None = None) -> AgentResult:
        approval = APPROVAL_RE.search(user_message)
        if approval:
            return self._execute_approved(db, session_id, approval.group(1))
        messages = list(history if history is not None else self.history(db, session_id))
        messages.append({"role": "user", "content": user_message})
        ctx = ToolContext(providers=self.providers, session_id=session_id, db=db, changes=self.change_service)
        tools = self.registry.specs()
        tool_calls: list[dict] = []
        warnings: list[str] = []
        total_in = total_out = 0
        model = ""
        request_id = None
        rejects = 0
        nudged = False
        verify_nudged = False
        last_text = ""
        seen: dict[str, int] = {}
        change_plan: dict | None = None

        prefetch = self._prefetch(user_message, ctx)
        if prefetch:
            compact, prefetch_call = prefetch
            tool_calls.append(prefetch_call)
            db.add(ToolCallRecord(session_id=session_id, name="get_incident_context",
                                  args_json=json.dumps(prefetch_call["args"], ensure_ascii=False),
                                  result_text=compact, status="ok", duration_ms=0))
            db.commit()
            tools = [s for s in tools if s["name"] == "submit_assessment"]
            messages[-1]["content"] = (
                user_message
                + "\n\n【已预取上下文（模拟数据）】\n" + compact
                + "\n\n请直接调用 submit_assessment 交卷：summary ≤300 字，最多 3 条假设、4 条建议、3 条不确定项；"
                  "不要重复查询，不要输出进度说明。"
            )

        for turn in range(1, self.settings.max_turns + 1):
            if total_in >= self.settings.max_input_tokens:
                warnings.append(f"输入 token 已超过上限（{self.settings.max_input_tokens}），提前停止。")
                break
            resp = self.llm.complete(self.system, messages, tools, max_tokens=MAX_OUTPUT_TOKENS)
            total_in += resp.input_tokens
            total_out += resp.output_tokens
            model = resp.model or model
            request_id = resp.request_id or request_id
            db.add(LLMUsageRecord(session_id=session_id, model=resp.model,
                                  input_tokens=resp.input_tokens, output_tokens=resp.output_tokens))
            db.commit()

            blocks = list(resp.content or [])
            messages.append({"role": "assistant", "content": blocks})
            uses = [b for b in blocks if b.get("type") == "tool_use"]
            last_text = _text_of(blocks) or last_text

            if not uses:
                if change_plan is not None and change_plan.get("status") == "succeeded" and not verify_nudged:
                    verify_nudged = True
                    messages.append({"role": "user", "content":
                                     f"变更已执行，请立即调用 verify_change(plan_id={change_plan.get('plan_id')}) 回读验证，不要直接结束。"})
                    continue
                if change_plan is not None:
                    if change_plan.get("status") == "succeeded":
                        warnings.append("变更已执行但未完成回读验证。")
                    return AgentResult(reply=last_text or "变更计划已创建，等待批准后再执行。",
                                       tool_calls=tool_calls,
                                       usage=Usage(model=model, input_tokens=total_in, output_tokens=total_out,
                                                   total_tokens=total_in + total_out, request_id=request_id),
                                       warnings=warnings, change_plan=change_plan)
                if not nudged:
                    nudged = True
                    messages.append({"role": "user", "content":
                                     "请继续：需要数据就调用工具；否则立即调用 submit_assessment 交卷。不要只输出进度说明。"})
                    continue
                warnings.append("模型没有调用 submit_assessment，已返回文字结果，结构未经校验。")
                return AgentResult(reply=last_text or "模型没有给出结论。", tool_calls=tool_calls,
                                   usage=Usage(model=model, input_tokens=total_in, output_tokens=total_out,
                                               total_tokens=total_in + total_out, request_id=request_id),
                                   warnings=warnings)

            results = []
            for use in uses:
                name = str(use.get("name", ""))
                args = use.get("input")
                use_id = use.get("id")
                if not isinstance(args, dict):
                    results.append({"type": "tool_result", "tool_use_id": use_id,
                                    "content": json.dumps({"error": "参数必须是 JSON 对象"}, ensure_ascii=False)})
                    continue

                if name == "submit_assessment":
                    try:
                        assessment = Assessment.model_validate(args)
                    except ValidationError as exc:
                        rejects += 1
                        errors = [f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()[:8]]
                        if rejects >= MAX_SUBMIT_REJECTS:
                            warnings.append("submit_assessment 连续不合格，返回文字结果。")
                            return AgentResult(reply=last_text or "诊断未能按格式交卷。", tool_calls=tool_calls,
                                               usage=Usage(model=model, input_tokens=total_in, output_tokens=total_out,
                                                           total_tokens=total_in + total_out, request_id=request_id),
                                               warnings=warnings)
                        results.append({"type": "tool_result", "tool_use_id": use_id,
                                        "content": "交卷不合格，请修正后重新调用 submit_assessment：\n- " + "\n- ".join(errors)})
                        continue
                    return AgentResult(reply=assessment.summary, assessment=assessment, tool_calls=tool_calls,
                                       usage=Usage(model=model, input_tokens=total_in, output_tokens=total_out,
                                                   total_tokens=total_in + total_out, request_id=request_id),
                                       warnings=warnings, change_plan=change_plan)

                key = name + json.dumps(args, ensure_ascii=False, sort_keys=True, default=str)
                seen[key] = seen.get(key, 0) + 1
                if seen[key] > 2:
                    results.append({"type": "tool_result", "tool_use_id": use_id,
                                    "content": "重复调用已跳过；请用已有数据交卷。"})
                    continue

                started = time.monotonic()
                content, status = self.registry.execute(name, args, ctx)
                duration = int((time.monotonic() - started) * 1000)
                content = _clip(content)
                preview = content[:400] + ("…" if len(content) > 400 else "")
                tool_calls.append({"name": name, "args": args, "result_preview": preview,
                                   "status": status, "duration_ms": duration})
                db.add(ToolCallRecord(session_id=session_id, name=name,
                                      args_json=json.dumps(args, ensure_ascii=False, default=str),
                                      result_text=content, status=status, duration_ms=duration))
                db.commit()
                if name in ("propose_change", "execute_change", "verify_change"):
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed.get("plan"), dict):
                            change_plan = parsed["plan"]
                    except (ValueError, AttributeError):
                        pass
                results.append({"type": "tool_result", "tool_use_id": use_id, "content": content})

            messages.append({"role": "user", "content": results})

        warnings.append(f"达到最大轮数 {self.settings.max_turns}，未完成结构化交卷。")
        return AgentResult(reply=last_text or "诊断未完成，请缩小问题范围后重试。", tool_calls=tool_calls,
                           usage=Usage(model=model, input_tokens=total_in, output_tokens=total_out,
                                       total_tokens=total_in + total_out, request_id=request_id),
                           warnings=warnings, change_plan=change_plan)
