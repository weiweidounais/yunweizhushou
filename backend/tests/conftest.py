from __future__ import annotations

import os
import tempfile
from dataclasses import replace

# 必须在导入 app 之前设置，避免读到真实 Key / 生产数据库。
_TMP = tempfile.mkdtemp(prefix="dcops-tests-")
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["MODEL_API_KEY"] = "fake-for-test"
os.environ["READ_ONLY_MODE"] = "true"
os.environ["MAX_TURNS"] = "8"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import reset_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.llm import LLMResponse, ScriptedLLM  # noqa: E402
from app.services.providers.mock import MockProviderSet  # noqa: E402

ASSESSMENT = {
    "summary": "Gi1/0/24 光模块劣化，导致端口 flapping 与 CRC 错包增长。",
    "impact": "核心交换机上联业务可能出现瞬断，影响 A 机房部分服务器。",
    "hypotheses": [
        {
            "cause": "光模块 RX 功率低导致链路不稳定",
            "confidence": "high",
            "evidence": ["RX 功率 -12.8 dBm，低于 -8 dBm 阈值", "CRC 2 小时内从 3 增至 220"],
            "falsification": "若更换光模块后 CRC 仍增长，需排查对端端口",
        }
    ],
    "recommendations": [
        {
            "step": "切换备用链路，检查并更换 Gi1/0/24 光模块",
            "risk": "medium",
            "requires_change": True,
            "rollback": "确认原链路恢复后切回；保留旧模块",
        }
    ],
    "unknowns": ["对端光模块状态尚未检查"],
}


def tool_use(name: str, args: dict, call_id: str = "call-1") -> LLMResponse:
    return LLMResponse(content=[{"type": "tool_use", "id": call_id, "name": name, "input": args}],
                       stop_reason="tool_use", input_tokens=100, output_tokens=50, model="mock")


def submit(assessment: dict, call_id: str = "call-submit") -> LLMResponse:
    return LLMResponse(content=[{"type": "tool_use", "id": call_id, "name": "submit_assessment",
                                 "input": assessment}],
                       stop_reason="tool_use", input_tokens=120, output_tokens=80, model="mock")


def text_response(text: str) -> LLMResponse:
    return LLMResponse(content=[{"type": "text", "text": text}], stop_reason="end_turn",
                       input_tokens=10, output_tokens=5, model="mock")


def make_client(responses: list[LLMResponse], max_turns: int = 8, fast_mode: bool = False):
    llm = ScriptedLLM(responses)
    app = create_app(llm=llm, providers=MockProviderSet(),
                     app_settings=replace(settings, max_turns=max_turns, fast_mode=fast_mode))
    return TestClient(app), llm


@pytest.fixture(autouse=True)
def _clean_db():
    reset_db()
    yield


@pytest.fixture()
def client_and_llm():
    return make_client
