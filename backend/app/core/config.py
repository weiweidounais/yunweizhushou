"""集中配置：只从环境变量 / backend/.env 读取，不把密钥写进代码。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PRODUCT_ROOT / "backend"
DATA_DIR = PRODUCT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BACKEND_ROOT / ".env", override=False)


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    model_provider: str = os.getenv("MODEL_PROVIDER", "deepseek")
    model_format: str = os.getenv("MODEL_FORMAT", "anthropic")
    model_name: str = os.getenv("MODEL_NAME", "deepseek-flash")
    model_base_url: str = os.getenv("MODEL_BASE_URL", "https://api.deepseek.com/anthropic")
    model_api_key: str = os.getenv("MODEL_API_KEY", "")
    max_turns: int = int(os.getenv("MAX_TURNS", "4"))
    max_input_tokens: int = int(os.getenv("MAX_INPUT_TOKENS", "120000"))
    read_only_mode: bool = _bool("READ_ONLY_MODE", True)
    fast_mode: bool = _bool("FAST_MODE", True)
    policy_mode: str = os.getenv("POLICY_MODE", "approval")
    approval_ttl_minutes: int = int(os.getenv("APPROVAL_TTL_MINUTES", "15"))
    monthly_budget_cny: float = float(os.getenv("MONTHLY_BUDGET_CNY", "50"))
    database_url: str = os.getenv("DATABASE_URL") or f"sqlite:///{DATA_DIR / 'app.db'}"
    backend_port: int = int(os.getenv("BACKEND_PORT", "8010"))
    model_timeout_seconds: float = float(os.getenv("MODEL_TIMEOUT_SECONDS", "90"))

    @property
    def model_configured(self) -> bool:
        return bool(self.model_api_key.strip()) and not self.model_api_key.startswith("fake-")


settings = Settings()
