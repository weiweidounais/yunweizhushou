#!/usr/bin/env python3
"""真实模型冒烟：阶段 2-1 只读诊断 / 阶段 2-2 变更审批链路。

用法：backend/.venv/bin/python scripts/smoke.py [--stage 阶段2-1|阶段2-2]
Key 从 backend/.env 读取；脚本不打印 Key，也不打印完整输入/输出。
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("APP_ENV", "smoke")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp(prefix='dcops-smoke-')}/smoke.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.schemas.chat import Assessment  # noqa: E402

DIAG_QUESTION = "core-sw-01 昨晚 22:00 开始丢包，什么原因？"
CHANGE_QUESTION = "帮我隔离 core-sw-01 的 Gi1/0/24 端口，理由：光模块劣化导致端口抖动"


def write_record(stage: str, model: str, chain: str, request_id: str, input_tokens: int,
                 output_tokens: int, elapsed: float, result: str, note: str) -> Path:
    out_dir = ROOT / "docs" / "evidence" / stage
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "冒烟记录.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = (f"| {now} | {chain} | {request_id} | {input_tokens} | {output_tokens} | "
           f"- | {elapsed:.1f}s | {note} | 0 | {result} |")
    content = f"""# 冒烟记录（冒烟脚本自动写入，不得手填）
- 产品：数据中心运维助理
- 阶段：{stage}
- 模型：{model}
- 写入时间：{now}

| 时间 | 链路 | 请求 ID | 输入 token | 输出 token | 首字耗时 | 总耗时 | 结构校验 | 重试次数 | 结果 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{row}
"""
    path.write_text(content, encoding="utf-8")
    return path


def _tokens(data: dict) -> tuple[int, int]:
    u = data.get("usage") or {}
    return int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0)


def run_diagnosis(client: TestClient, stage: str) -> int:
    session = client.post("/api/sessions", json={"title": "冒烟"}).json()
    started = time.monotonic()
    resp = client.post(f"/api/sessions/{session['id']}/chat", json={"message": DIAG_QUESTION})
    elapsed = time.monotonic() - started
    if resp.status_code != 200:
        detail = resp.json().get("error", {}).get("message", "未知错误")
        path = write_record(stage, "-", "只读诊断：core-sw-01 丢包", "-", 0, 0, elapsed, "失败", f"HTTP {resp.status_code}：{detail}")
        print(f"冒烟失败：HTTP {resp.status_code}；记录：{path}")
        return 1
    data = resp.json()
    try:
        valid = bool(data.get("assessment")) and Assessment.model_validate(data["assessment"]) is not None
    except Exception:  # noqa: BLE001
        valid = False
    tin, tout = _tokens(data)
    usage = data.get("usage") or {}
    path = write_record(stage, usage.get("model") or "-", "只读诊断：core-sw-01 丢包",
                        usage.get("request_id") or "-", tin, tout, elapsed,
                        "通过" if valid else "失败", "首测合规" if valid else "未交卷/结构不合规")
    print(f"冒烟{'通过' if valid else '失败'}：{elapsed:.1f}s；记录：{path}")
    return 0 if valid else 1


def run_change(client: TestClient, stage: str) -> int:
    session = client.post("/api/sessions", json={"title": "变更冒烟"}).json()
    started = time.monotonic()
    first = client.post(f"/api/sessions/{session['id']}/chat", json={"message": CHANGE_QUESTION})
    if first.status_code != 200:
        elapsed = time.monotonic() - started
        detail = first.json().get("error", {}).get("message", "未知错误")
        path = write_record(stage, "-", "变更：隔离 Gi1/0/24", "-", 0, 0, elapsed, "失败", f"HTTP {first.status_code}：{detail}")
        print(f"冒烟失败：HTTP {first.status_code}；记录：{path}")
        return 1
    first_data = first.json()
    plan = first_data.get("change_plan")
    if not plan or not plan.get("plan_id"):
        elapsed = time.monotonic() - started
        path = write_record(stage, "-", "变更：隔离 Gi1/0/24", "-", 0, 0, elapsed, "失败", "模型没有创建变更计划")
        print(f"冒烟失败：没有变更计划；记录：{path}")
        return 1
    approve = client.post(f"/api/changes/{plan['plan_id']}/approve", json={"comment": "冒烟批准"})
    if approve.status_code != 200:
        elapsed = time.monotonic() - started
        path = write_record(stage, "-", "变更：隔离 Gi1/0/24", "-", 0, 0, elapsed, "失败", f"审批失败：{approve.status_code}")
        print(f"冒烟失败：审批失败；记录：{path}")
        return 1
    second = client.post(f"/api/sessions/{session['id']}/chat",
                         json={"message": f"已批准 plan_id={plan['plan_id']}，请执行并回读验证。"})
    elapsed = time.monotonic() - started
    if second.status_code != 200:
        detail = second.json().get("error", {}).get("message", "未知错误")
        path = write_record(stage, "-", "变更：隔离 Gi1/0/24", "-", 0, 0, elapsed, "失败", f"执行 HTTP {second.status_code}：{detail}")
        print(f"冒烟失败：执行 HTTP {second.status_code}；记录：{path}")
        return 1
    second_data = second.json()
    final_plan = second_data.get("change_plan") or {}
    tools = [t.get("name") for t in second_data.get("tool_calls", [])]
    chain = client.get("/api/audit/verify").json()
    valid = (final_plan.get("status") == "verified"
             and "execute_change" in tools and "verify_change" in tools
             and chain.get("valid") is True)
    detail = (f"plan={final_plan.get('status')}; tools={','.join(tools)}; chain={chain.get('valid')}")
    tin, tout = _tokens(first_data)
    tin2, tout2 = _tokens(second_data)
    usage = first_data.get("usage") or {}
    path = write_record(stage, usage.get("model") or "-", "变更：隔离 Gi1/0/24",
                        usage.get("request_id") or "-", tin + tin2, tout + tout2, elapsed,
                        "通过" if valid else "失败",
                        "首测合规：审批+执行+回读+审计链" if valid else detail)
    print(f"冒烟{'通过' if valid else '失败'}：{elapsed:.1f}s；记录：{path}")
    return 0 if valid else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="阶段2-1", choices=["阶段2-1", "阶段2-2", "阶段3-1", "阶段3-2", "阶段3-3"])
    args = parser.parse_args()
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        health = client.get("/api/health")
        if health.status_code != 200:
            print(f"健康检查失败：{health.status_code}")
            return 1
        if args.stage == "阶段2-2":
            return run_change(client, args.stage)
        return run_diagnosis(client, args.stage)


if __name__ == "__main__":
    raise SystemExit(main())
