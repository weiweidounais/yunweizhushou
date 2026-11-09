"""演示用连接器：读 backend/app/data 下的 JSON/Markdown，不碰真实系统。"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from app.services.providers.base import Alarm, Asset, Edge, Runbook

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

CHECK_IDS = {
    "ping": "连通性",
    "port_status": "端口状态",
    "raid": "RAID 状态",
    "smart": "磁盘 SMART",
    "temp": "温度",
    "fan": "风扇",
}


def _load(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


class MockProviderSet:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._assets = [Asset(**a) for a in _load("assets.json")["assets"]]
        self._alarms = [Alarm(**a) for a in _load("alarms.json")["alarms"]]
        self._metrics = _load("metrics.json")["metrics"]
        self._edges = [Edge(**e) for e in _load("topology.json")["edges"]]
        self._runbooks = self._load_runbooks()

    def _load_runbooks(self) -> list[Runbook]:
        runbooks: list[Runbook] = []
        for path in sorted((self.data_dir / "runbooks").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
            if not match:
                continue
            meta = yaml.safe_load(match.group(1)) or {}
            body = match.group(2).strip()
            runbooks.append(Runbook(
                id=str(meta.get("id", path.stem)),
                title=str(meta.get("title", path.stem)),
                applies_to=list(meta.get("applies_to", [])),
                symptoms=[str(s) for s in meta.get("symptoms", [])],
                risk=str(meta.get("risk", "medium")),
                requires_change=bool(meta.get("requires_change", False)),
                owner=str(meta.get("owner", "")),
                version=int(meta.get("version", 1)),
                reviewed_at=str(meta.get("reviewed_at", "")),
                body=body,
            ))
        return runbooks

    # -- 资产 -------------------------------------------------------------
    def resolve_asset(self, query: str) -> tuple[Asset | None, list[Asset]]:
        q = (query or "").strip().lower()
        if not q:
            return None, []
        exact = [a for a in self._assets if q in {a.id.lower(), a.name.lower(), *(x.lower() for x in a.aliases)}]
        if len(exact) == 1:
            return exact[0], []
        fuzzy = [a for a in self._assets if q in a.id.lower() or q in a.name.lower()
                 or any(q in x.lower() or x.lower() in q for x in a.aliases)]
        if len(fuzzy) == 1:
            return fuzzy[0], []
        return None, fuzzy or exact

    def get_asset(self, asset_id: str) -> Asset | None:
        return next((a for a in self._assets if a.id == asset_id), None)

    def list_assets(self) -> list[Asset]:
        return list(self._assets)

    # -- 告警 -------------------------------------------------------------
    def list_alarms(self, asset_id: str | None = None, status: str | None = None,
                    severity: str | None = None) -> list[Alarm]:
        rows = self._alarms
        if asset_id:
            rows = [a for a in rows if a.asset_id == asset_id]
        if status:
            rows = [a for a in rows if a.status == status]
        if severity:
            rows = [a for a in rows if a.severity == severity]
        return list(rows)

    # -- 指标 -------------------------------------------------------------
    def query_metrics(self, asset_id: str, metrics: list[str], window_hours: int = 24) -> dict:
        asset_metrics = self._metrics.get(asset_id, {})
        found: dict = {}
        missing: list[str] = []
        for name in metrics:
            if name in asset_metrics:
                found[name] = asset_metrics[name]
            else:
                missing.append(name)
        return {
            "asset_id": asset_id,
            "window_hours": window_hours,
            "metrics": found,
            "missing": missing,
            "available": sorted(asset_metrics.keys()),
            "note": "模拟指标，仅用于演示。",
        }

    # -- 拓扑 -------------------------------------------------------------
    def neighbors(self, asset_id: str) -> list[Edge]:
        return [e for e in self._edges if e.source == asset_id or e.target == asset_id]

    # -- runbook ----------------------------------------------------------
    def search_runbooks(self, query: str, asset_type: str | None = None) -> list[dict]:
        words = [w for w in re.split(r"[\s,，。;；/]+", query or "") if w]
        results = []
        for rb in self._runbooks:
            if asset_type and asset_type not in rb.applies_to:
                continue
            haystack = " ".join([rb.title, *rb.symptoms, rb.body])
            score = sum(1 for w in words if w and w in haystack)
            if score or not words:
                results.append((score, rb))
        results.sort(key=lambda x: (-x[0], x[1].id))
        out = []
        for _, rb in results[:3]:
            snippet = " ".join(rb.body.split())[:500]
            out.append({
                "id": rb.id,
                "title": rb.title,
                "version": rb.version,
                "owner": rb.owner,
                "reviewed_at": rb.reviewed_at,
                "risk": rb.risk,
                "requires_change": rb.requires_change,
                "snippet": snippet,
            })
        return out

    # -- 只读检查 ---------------------------------------------------------
    def readonly_check(self, asset_id: str, check_id: str) -> dict:
        asset = self.get_asset(asset_id)
        if not asset:
            return {"error": f"资产不存在：{asset_id}"}
        if check_id not in CHECK_IDS:
            return {"error": f"不支持的检查项：{check_id}，可用：{sorted(CHECK_IDS)}"}
        if check_id == "ping":
            return {"check": check_id, "asset_id": asset_id, "status": "pass", "summary": "管理 IP 可达，平均 RTT 1.2ms", "details": {}}
        if check_id == "port_status":
            if asset_id == "core-sw-01":
                return {"check": check_id, "asset_id": asset_id, "status": "fail", "summary": "Gi1/0/24 状态 flapping，RX 功率 -12.8 dBm", "details": {"interface": "Gi1/0/24", "flaps": 18}}
            return {"check": check_id, "asset_id": asset_id, "status": "pass", "summary": "端口 Up，无 flaps", "details": {}}
        if check_id == "raid":
            if asset_id == "db-prod-01":
                return {"check": check_id, "asset_id": asset_id, "status": "fail", "summary": "RAID10 degraded，sdb 离线", "details": {"controller": "PERC H755", "offline_disks": ["sdb"]}}
            return {"check": check_id, "asset_id": asset_id, "status": "pass", "summary": "RAID 正常", "details": {}}
        if check_id == "smart":
            return {"check": check_id, "asset_id": asset_id, "status": "warn" if asset_id == "db-prod-01" else "pass", "summary": "sdb SMART 出现重映射扇区增长" if asset_id == "db-prod-01" else "SMART 正常", "details": {}}
        if check_id == "temp":
            if asset_id == "hvac-01":
                return {"check": check_id, "asset_id": asset_id, "status": "fail", "summary": "回风温度 31.2°C，高于阈值 27°C", "details": {"return_temp_c": 31.2}}
            return {"check": check_id, "asset_id": asset_id, "status": "pass", "summary": "温度正常", "details": {}}
        return {"check": check_id, "asset_id": asset_id, "status": "pass", "summary": "风扇转速正常", "details": {}}
