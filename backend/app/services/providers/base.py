"""连接器抽象：真实系统只需实现同一组方法，工具层不改。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Asset:
    id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    type: str = ""
    env: str = "prod"
    site: str = ""
    rack: str = ""
    criticality: str = "P2"
    owner: str = ""
    vendor: str = ""
    model: str = ""
    os: str = ""
    services: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=list)
    no_touch: bool = False

    def public(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "env": self.env,
            "site": self.site,
            "rack": self.rack,
            "criticality": self.criticality,
            "owner": self.owner,
            "vendor": self.vendor,
            "model": self.model,
            "os": self.os,
            "services": self.services,
            "allowed_actions": self.allowed_actions,
            "no_touch": self.no_touch,
        }


@dataclass(frozen=True)
class Alarm:
    id: str
    source: str
    asset_id: str
    severity: str
    name: str
    description: str
    first_seen: str
    last_seen: str
    status: str
    labels: dict = field(default_factory=dict)

    def public(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "asset_id": self.asset_id,
            "severity": self.severity,
            "name": self.name,
            "description": self.description,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "status": self.status,
            "labels": self.labels,
        }


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    direction: str
    type: str


@dataclass(frozen=True)
class Runbook:
    id: str
    title: str
    applies_to: list[str]
    symptoms: list[str]
    risk: str
    requires_change: bool
    owner: str
    version: int
    reviewed_at: str
    body: str


class Providers(Protocol):
    def resolve_asset(self, query: str) -> tuple[Asset | None, list[Asset]]: ...
    def get_asset(self, asset_id: str) -> Asset | None: ...
    def list_alarms(self, asset_id: str | None = None, status: str | None = None,
                    severity: str | None = None) -> list[Alarm]: ...
    def query_metrics(self, asset_id: str, metrics: list[str], window_hours: int = 24) -> dict: ...
    def neighbors(self, asset_id: str) -> list[Edge]: ...
    def search_runbooks(self, query: str, asset_type: str | None = None) -> list[dict]: ...
    def readonly_check(self, asset_id: str, check_id: str) -> dict: ...
