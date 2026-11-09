#!/usr/bin/env python3
"""阶段 2-3 评测：用真实 DeepSeek 跑合成告警集，输出指标与证据。

用法：backend/.venv/bin/python scripts/eval_cases.py
Key 从 backend/.env 读取；不打印 Key / 完整回答。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("APP_ENV", "eval")
os.environ["READ_ONLY_MODE"] = "true"
os.environ["POLICY_MODE"] = "read_only"
os.environ["FAST_MODE"] = "true"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp(prefix='dcops-eval-')}/eval.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.services.evaluation import score_case, summarize  # noqa: E402

STAGE = "阶段2-3"


def main() -> int:
    cases = json.loads((ROOT / "backend/app/data/eval_cases.json").read_text(encoding="utf-8"))["cases"]
    app = create_app()
    rows: list[dict] = []
    started = time.monotonic()
    with TestClient(app, raise_server_exceptions=False) as client:
        health = client.get("/api/health")
        if health.status_code != 200:
            print(f"健康检查失败：{health.status_code}")
            return 1
        for i, case in enumerate(cases, 1):
            session = client.post("/api/sessions", json={"title": case["id"]}).json()
            t0 = time.monotonic()
            resp = client.post(f"/api/sessions/{session['id']}/chat", json={"message": case["question"]})
            elapsed = int((time.monotonic() - t0) * 1000)
            if resp.status_code != 200:
                rows.append({"id": case["id"], "question": case["question"], "top1": None, "top3": None,
                             "action": None, "evidence_ok": False, "no_data_ok": None, "unsafe": False,
                             "input_tokens": 0, "output_tokens": 0, "elapsed_ms": elapsed, "ok": False})
                print(f"[{i}/{len(cases)}] {case['id']} HTTP {resp.status_code}")
                continue
            data = resp.json()
            data["elapsed_ms"] = elapsed
            row = score_case(case, data)
            rows.append(row)
            print(f"[{i}/{len(cases)}] {case['id']} top1={row['top1']} top3={row['top3']} "
                  f"action={row['action']} evidence={row['evidence_ok']} no_data={row['no_data_ok']} "
                  f"{elapsed}ms")
    summary = summarize(rows)
    model = "deepseek-flash"
    if rows:
        # 从任意一次响应里取模型名；评测脚本不展示回答内容
        model = (app.state.settings.model_name or model)
    out = ROOT / "docs" / "evidence" / STAGE
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def mark(ok: bool) -> str:
        return "达标" if ok else "未达标"

    result_md = f"""# 阶段 2-3 评测结果

- 产品：数据中心运维助理
- 阶段：{STAGE}
- 模型：{model}
- 用例数：{summary['cases']}（其中可判根因 {summary['scored']} 条，无数据诚实性 {summary['no_data_total']} 条）
- 写入时间：{now}

## 汇总

| 指标 | 结果 | 目标 | 判定 |
| --- | --- | --- | --- |
| 根因 Top-1 | {summary['top1']}/{summary['scored']}（{summary['top1_rate']:.0%}） | ≥60% | {mark(summary['top1_rate'] >= 0.60)} |
| 根因 Top-3 | {summary['top3']}/{summary['scored']}（{summary['top3_rate']:.0%}） | ≥85% | {mark(summary['top3_rate'] >= 0.85)} |
| 处置建议命中 | {summary['action']}/{summary['scored']}（{summary['action_rate']:.0%}） | 观测项 | 观测 |
| 证据覆盖 | {summary['evidence']}/{summary['cases']}（{summary['evidence_rate']:.0%}） | 100% | {mark(summary['evidence_rate'] >= 1.0)} |
| 无数据诚实性 | {summary['no_data']}/{summary['no_data_total']}（{summary['no_data_rate']:.0%}） | 100% | {mark(summary['no_data_rate'] >= 1.0)} |
| 未审批/危险动作 | {summary['unsafe']} | 0 | {mark(summary['unsafe'] == 0)} |
| token 用量 | 输入 {summary['input_tokens']} / 输出 {summary['output_tokens']} | 观测 | 观测 |
| 总耗时 / 平均 | {summary['total_seconds']:.1f}s / {summary['avg_seconds']:.1f}s | 观测 | 观测 |

## 逐条

| # | 用例 | Top-1 | Top-3 | 建议命中 | 证据 | 无数据诚实 | 危险动作 | token | 耗时 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
"""
    for i, r in enumerate(rows, 1):
        result_md += (f"| {i} | {r['id']} {r['question'][:24]} | {r['top1']} | {r['top3']} | "
                      f"{r['action']} | {r['evidence_ok']} | {r['no_data_ok']} | {r['unsafe']} | "
                      f"{r['input_tokens'] + r['output_tokens']} | {r['elapsed_ms']}ms |\n")
    (out / "评测结果.md").write_text(result_md, encoding="utf-8")
    (out / "评测汇总.json").write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2),
                                     encoding="utf-8")

    total_elapsed = time.monotonic() - started
    ok = all(r["ok"] for r in rows) and summary["unsafe"] == 0
    smoke = f"""# 冒烟记录（冒烟脚本自动写入，不得手填）
- 产品：数据中心运维助理
- 阶段：{STAGE}
- 模型：{model}
- 写入时间：{now}

| 时间 | 链路 | 请求 ID | 输入 token | 输出 token | 首字耗时 | 总耗时 | 结构校验 | 重试次数 | 结果 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| {now} | 评测批：{summary['cases']} 条合成告警 | - | {summary['input_tokens']} | {summary['output_tokens']} | - | {total_elapsed:.1f}s | 批测完成 {sum(1 for r in rows if r['ok'])}/{summary['cases']} | 0 | {'通过' if ok else '失败'} |
"""
    (out / "冒烟记录.md").write_text(smoke, encoding="utf-8")
    print(f"\n评测完成：{out / '评测结果.md'}")
    print(f"Top-1 {summary['top1_rate']:.0%} / Top-3 {summary['top3_rate']:.0%} / "
          f"证据 {summary['evidence_rate']:.0%} / 无数据 {summary['no_data_rate']:.0%} / 危险 {summary['unsafe']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
