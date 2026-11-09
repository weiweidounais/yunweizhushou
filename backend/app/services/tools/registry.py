"""只读工具：模型只能通过这里定义的函数触达数据。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Literal

from pydantic import BaseModel, Field, ValidationError

from app.schemas.chat import Assessment
from app.services.changes import ChangeService
from app.services.providers.base import Asset
from app.services.providers.mock import MockProviderSet

METRICS_BY_TYPE = {
    "switch": ["port_errors", "optical_rx_power_dbm", "cpu_util"],
    "server": ["disk_latency_ms", "raid_degraded", "cpu_util", "memory_util"],
    "storage": ["pool_used_pct", "disk_latency_ms"],
    "cooling": ["return_temp_c", "humidity_pct"],
}


class IncidentContextInput(BaseModel):
    asset: str = Field(min_length=1, max_length=100, description="资产 ID、名称、IP 或别名")
    window_hours: int = Field(default=24, ge=1, le=168, description="回看小时数")


class MetricsInput(BaseModel):
    asset: str = Field(min_length=1, max_length=100)
    metrics: list[str] = Field(min_length=1, max_length=10)
    window_hours: int = Field(default=24, ge=1, le=168)


class AlarmsInput(BaseModel):
    asset: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default="active", max_length=20)
    severity: str | None = Field(default=None, max_length=20)


class AssetInput(BaseModel):
    asset: str = Field(min_length=1, max_length=100)


class RunbookInput(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    asset_type: str | None = Field(default=None, max_length=30)


class CheckInput(BaseModel):
    asset: str = Field(min_length=1, max_length=100)
    check_id: str = Field(min_length=1, max_length=30)


class TodoInput(BaseModel):
    steps: list[str] = Field(min_length=1, max_length=10)


class ProposeChangeInput(BaseModel):
    asset: str = Field(min_length=1, max_length=100, description="资产 ID、名称、IP 或别名")
    action: Literal["isolate_port", "restart_service", "restart_host", "power_off", "config_change"] = Field(
        description="变更动作；power_off/restart_host 等高风险动作会被策略拒绝或要求审批")
    params: dict = Field(default_factory=dict, description="动作参数，例如 {\"port\": \"Gi1/0/24\"}")
    reason: str = Field(min_length=1, max_length=300, description="变更理由")
    impact: str = Field(default="", max_length=300, description="影响面")
    rollback: str = Field(min_length=1, max_length=300, description="回滚方式，必填")
    window_start: str | None = Field(default=None, max_length=40, description="执行窗口开始，可空")
    window_end: str | None = Field(default=None, max_length=40, description="执行窗口结束，可空")


class ExecuteChangeInput(BaseModel):
    plan_id: str = Field(min_length=1, max_length=64, description="propose_change 返回的 plan_id")


class VerifyChangeInput(BaseModel):
    plan_id: str = Field(min_length=1, max_length=64)


@dataclass
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[BaseModel, "ToolContext"], dict]

    def spec(self) -> dict:
        return {"name": self.name, "description": self.description,
                "input_schema": self.input_model.model_json_schema()}


@dataclass
class ToolContext:
    providers: MockProviderSet
    session_id: str
    db: object | None = None
    changes: ChangeService | None = None


def _resolve(ctx: ToolContext, query: str) -> tuple[Asset | None, dict | None]:
    asset, candidates = ctx.providers.resolve_asset(query)
    if asset:
        return asset, None
    if candidates:
        return None, {"error": "资产不明确，请确认是哪一个", "candidates": [a.id for a in candidates]}
    return None, {"error": f"找不到资产：{query}"}


def _trim_metrics(result: dict) -> dict:
    metrics = {}
    for name, m in (result.get("metrics") or {}).items():
        metrics[name] = {**m, "points": (m.get("points") or [])[-3:]}
    return {**result, "metrics": metrics, "points_note": "每个指标仅保留最近 3 个采样点。"}


def _incident_context(args: IncidentContextInput, ctx: ToolContext) -> dict:
    asset, error = _resolve(ctx, args.asset)
    if error:
        return error
    assert asset
    alarms = ctx.providers.list_alarms(asset.id, status="active")[:5]
    metric_names = METRICS_BY_TYPE.get(asset.type, ["cpu_util"])
    metrics = _trim_metrics(ctx.providers.query_metrics(asset.id, metric_names, args.window_hours))
    edges = ctx.providers.neighbors(asset.id)[:4]
    rb_query = " ".join([asset.type, *[a.name for a in alarms]])
    runbooks = ctx.providers.search_runbooks(rb_query, asset_type=asset.type)[:2]
    for rb in runbooks:
        rb["snippet"] = (rb.get("snippet") or "")[:180]
    return {
        "asset": asset.public(),
        "active_alarms": [a.public() for a in alarms],
        "metrics": metrics,
        "topology": [{"source": e.source, "target": e.target, "direction": e.direction, "type": e.type} for e in edges],
        "runbooks": runbooks,
        "data_notes": ["当前为模拟数据；时间窗口为最近 %d 小时。" % args.window_hours],
    }


def _query_metrics(args: MetricsInput, ctx: ToolContext) -> dict:
    asset, error = _resolve(ctx, args.asset)
    if error:
        return error
    assert asset
    return _trim_metrics(ctx.providers.query_metrics(asset.id, args.metrics, args.window_hours))


def _query_alarms(args: AlarmsInput, ctx: ToolContext) -> dict:
    asset_id = None
    if args.asset:
        asset, error = _resolve(ctx, args.asset)
        if error:
            return error
        assert asset
        asset_id = asset.id
    rows = ctx.providers.list_alarms(asset_id, status=args.status or None, severity=args.severity or None)
    return {"alarms": [a.public() for a in rows], "count": len(rows)}


def _get_asset(args: AssetInput, ctx: ToolContext) -> dict:
    asset, error = _resolve(ctx, args.asset)
    if error:
        return error
    assert asset
    return {"asset": asset.public()}


def _search_topology(args: AssetInput, ctx: ToolContext) -> dict:
    asset, error = _resolve(ctx, args.asset)
    if error:
        return error
    assert asset
    edges = ctx.providers.neighbors(asset.id)
    return {"asset_id": asset.id, "edges": [
        {"source": e.source, "target": e.target, "direction": e.direction, "type": e.type} for e in edges
    ]}


def _search_runbook(args: RunbookInput, ctx: ToolContext) -> dict:
    results = ctx.providers.search_runbooks(args.query, asset_type=args.asset_type)[:2]
    for rb in results:
        rb["snippet"] = (rb.get("snippet") or "")[:180]
    return {"runbooks": results, "count": len(results)}


def _readonly_check(args: CheckInput, ctx: ToolContext) -> dict:
    asset, error = _resolve(ctx, args.asset)
    if error:
        return error
    assert asset
    return ctx.providers.readonly_check(asset.id, args.check_id)


def _todo_write(args: TodoInput, ctx: ToolContext) -> dict:
    return {"steps": args.steps, "note": "计划已记录；请按步骤继续，并在结论里说明进度。"}


def _propose_change(args: ProposeChangeInput, ctx: ToolContext) -> dict:
    if ctx.changes is None or ctx.db is None:
        return {"error": "变更服务未初始化"}
    plan = ctx.changes.propose(ctx.db, ctx.session_id, args.asset, args.action, args.params,
                               args.reason, args.impact, args.rollback,
                               args.window_start, args.window_end)
    return {"plan": plan, "message": "变更计划已创建，状态 pending_approval；请让用户先批准，再执行。"}


def _execute_change(args: ExecuteChangeInput, ctx: ToolContext) -> dict:
    if ctx.changes is None or ctx.db is None:
        return {"error": "变更服务未初始化"}
    return {"plan": ctx.changes.execute(ctx.db, args.plan_id)}


def _verify_change(args: VerifyChangeInput, ctx: ToolContext) -> dict:
    if ctx.changes is None or ctx.db is None:
        return {"error": "变更服务未初始化"}
    return {"plan": ctx.changes.verify(ctx.db, args.plan_id)}


def _submit_assessment(args: Assessment, ctx: ToolContext) -> dict:
    return {"ok": True}


def build_registry() -> "ToolRegistry":
    return ToolRegistry([
        Tool("get_incident_context", "一次拉取资产、活跃告警、关键指标、拓扑和 runbook，诊断首选。",
             IncidentContextInput, _incident_context),
        Tool("query_metrics", "按资产和指标名查询时序指标；没有的指标会返回 missing。",
             MetricsInput, _query_metrics),
        Tool("query_alarms", "按资产/状态/级别查询告警。", AlarmsInput, _query_alarms),
        Tool("get_asset", "查询资产详情（环境、关键级别、责任人、允许动作）。", AssetInput, _get_asset),
        Tool("search_topology", "查询资产的直接上下游。", AssetInput, _search_topology),
        Tool("search_runbook", "按症状/设备类型检索 runbook。", RunbookInput, _search_runbook),
        Tool("run_readonly_check", "执行预置只读检查（ping/port_status/raid/smart/temp/fan），不支持任意命令。",
             CheckInput, _readonly_check),
        Tool("todo_write", "记录多步诊断/处置计划。", TodoInput, _todo_write),
        Tool("propose_change", "创建变更计划；只创建计划，不执行。高风险动作会被策略拒绝。",
             ProposeChangeInput, _propose_change),
        Tool("execute_change", "执行已批准的变更计划；没有有效审批会被拒绝。",
             ExecuteChangeInput, _execute_change),
        Tool("verify_change", "变更执行后回读指标/告警，验证是否生效。",
             VerifyChangeInput, _verify_change),
        Tool("submit_assessment", "诊断完成时调用，提交结构化结论；参数不合格会被退回。",
             Assessment, _submit_assessment),
    ])


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self.tools = {t.name: t for t in tools}

    def specs(self) -> list[dict]:
        return [t.spec() for t in self.tools.values()]

    def names(self) -> list[str]:
        return list(self.tools)

    def execute(self, name: str, args: dict, ctx: ToolContext) -> tuple[str, str]:
        tool = self.tools.get(name)
        if tool is None:
            return json.dumps({"error": f"没有工具：{name}", "available": self.names()}, ensure_ascii=False), "error"
        if not isinstance(args, dict):
            return json.dumps({"error": "参数必须是 JSON 对象"}, ensure_ascii=False), "error"
        try:
            parsed = tool.input_model.model_validate(args)
        except ValidationError as exc:
            return json.dumps({"error": "参数不合法", "details": exc.errors()[:5]}, ensure_ascii=False, default=str), "error"
        try:
            result = tool.handler(parsed, ctx)
            return json.dumps(result, ensure_ascii=False, default=str), "ok"
        except Exception as exc:  # noqa: BLE001 - 工具失败交给模型处理
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), "error"
