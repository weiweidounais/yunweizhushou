"""模型接入：统一 LLMProvider，DeepSeek 走 Anthropic 兼容接口；测试用 ScriptedLLM。"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import Settings, settings as default_settings
from app.core.errors import LLMError


@dataclass
class LLMResponse:
    content: list[dict]
    stop_reason: str = "end_turn"
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    request_id: str | None = None
    raw: Any = field(default=None, repr=False)


class LLMClient(Protocol):
    def complete(self, system: str, messages: list[dict], tools: list[dict],
                 max_tokens: int = 2048) -> LLMResponse: ...


class AnthropicDeepSeekClient:
    """DeepSeek 的 Anthropic 兼容接口；正式换生产 API 时只换这个类。"""

    def __init__(self, settings: Settings = default_settings) -> None:
        self.settings = settings
        self._client = None

    def _client_or_raise(self):
        if not self.settings.model_configured:
            raise LLMError("模型未配置：请在 backend/.env 设置 MODEL_API_KEY")
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - 依赖缺失
                raise LLMError("未安装 anthropic SDK") from exc
            try:
                self._client = anthropic.Anthropic(
                    api_key=self.settings.model_api_key,
                    base_url=self.settings.model_base_url,
                    timeout=self.settings.model_timeout_seconds,
                    max_retries=0,
                )
            except Exception as exc:  # pragma: no cover - SDK 初始化异常
                raise LLMError(f"模型客户端初始化失败：{type(exc).__name__}") from exc
        return self._client

    def complete(self, system: str, messages: list[dict], tools: list[dict],
                 max_tokens: int = 2048) -> LLMResponse:
        import anthropic

        client = self._client_or_raise()
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = client.messages.create(
                    model=self.settings.model_name,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages,
                    tools=tools,
                )
                blocks = []
                for block in resp.content:
                    if hasattr(block, "model_dump"):
                        blocks.append(block.model_dump(exclude_none=True))
                    else:  # pragma: no cover
                        blocks.append(dict(block))
                usage = getattr(resp, "usage", None)
                return LLMResponse(
                    content=blocks,
                    stop_reason=str(getattr(resp, "stop_reason", "end_turn")),
                    input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                    output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
                    model=str(getattr(resp, "model", self.settings.model_name)),
                    request_id=getattr(resp, "id", None),
                    raw=resp,
                )
            except anthropic.APIStatusError as exc:
                last_exc = exc
                status = getattr(exc, "status_code", 0)
                if status in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if status in (401, 403):
                    raise LLMError("模型鉴权失败：请检查 MODEL_API_KEY") from exc
                raise LLMError(f"模型接口返回 {status}：请检查模型名/额度") from exc
            except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMError("模型接口超时或网络不可达，请稍后重试") from exc
            except Exception as exc:  # pragma: no cover - 兜底
                last_exc = exc
                raise LLMError(f"模型调用失败：{type(exc).__name__}") from exc
        raise LLMError(f"模型调用失败：{type(last_exc).__name__ if last_exc else 'unknown'}")


class ScriptedLLM:
    """测试替身：按顺序返回预设响应，不发真实请求。"""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def complete(self, system: str, messages: list[dict], tools: list[dict],
                 max_tokens: int = 2048) -> LLMResponse:
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        if not self.responses:
            return LLMResponse(content=[{"type": "text", "text": "（测试替身没有更多回复）"}],
                               model="mock", stop_reason="end_turn")
        return self.responses.pop(0)


def build_llm(settings: Settings = default_settings) -> LLMClient:
    if settings.model_format == "openai":
        return OpenAICompatClient(settings)
    return AnthropicDeepSeekClient(settings)


def _to_openai_messages(messages: list[dict]) -> list[dict]:
    """把 Anthropic 风格的 messages 转成 OpenAI chat/completions 的 messages。"""
    out: list[dict] = []
    for m in messages:
        role, content = m.get("role"), m.get("content")
        if role == "user" and isinstance(content, str):
            out.append({"role": "user", "content": content})
        elif role == "user" and isinstance(content, list):
            for b in content:
                if b.get("type") == "tool_result":
                    out.append({"role": "tool", "tool_call_id": b.get("tool_use_id"), "content": str(b.get("content", ""))})
                elif b.get("type") == "text":
                    out.append({"role": "user", "content": b.get("text", "")})
        elif role == "assistant" and isinstance(content, list):
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
            calls = []
            for b in content:
                if b.get("type") == "tool_use":
                    calls.append({
                        "id": b.get("id") or f"call_{len(calls)}",
                        "type": "function",
                        "function": {"name": b.get("name", ""),
                                     "arguments": json.dumps(b.get("input") or {}, ensure_ascii=False)},
                    })
            msg = {"role": "assistant", "content": text or None}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
    return out


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    return [{"type": "function", "function": {"name": t["name"],
                                               "description": t.get("description", ""),
                                               "parameters": t.get("input_schema", {})}} for t in tools]


class OpenAICompatClient:
    """OpenAI 兼容接口（DeepSeek /chat/completions）；不产生 thinking 块，演示更快。"""

    def __init__(self, settings: Settings = default_settings) -> None:
        self.settings = settings

    def complete(self, system: str, messages: list[dict], tools: list[dict],
                 max_tokens: int = 1600) -> LLMResponse:
        import httpx

        if not self.settings.model_configured:
            raise LLMError("模型未配置：请在 backend/.env 设置 MODEL_API_KEY")
        url = self.settings.model_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.model_name,
            "messages": [{"role": "system", "content": system}] + _to_openai_messages(messages),
            "tools": _to_openai_tools(tools),
            "tool_choice": "auto",
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.settings.model_api_key}"}
        last_error = "unknown"
        for attempt in range(3):
            try:
                resp = httpx.post(url, headers=headers, json=payload,
                                  timeout=self.settings.model_timeout_seconds)
            except httpx.TimeoutException as exc:
                last_error = "超时"
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMError("模型接口超时，请稍后重试") from exc
            except httpx.HTTPError as exc:
                last_error = type(exc).__name__
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMError("模型接口网络不可达，请稍后重试") from exc
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                last_error = f"HTTP {resp.status_code}"
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code == 401 or resp.status_code == 403:
                raise LLMError("模型鉴权失败：请检查 MODEL_API_KEY")
            if resp.status_code >= 400:
                raise LLMError(f"模型接口返回 {resp.status_code}：请检查模型名/额度")
            try:
                data = resp.json()
                choice = data["choices"][0]
                msg = choice.get("message") or {}
            except (ValueError, KeyError, IndexError) as exc:
                raise LLMError("模型返回格式异常") from exc
            blocks: list[dict] = []
            if msg.get("content"):
                blocks.append({"type": "text", "text": msg["content"]})
            for call in msg.get("tool_calls") or []:
                fn = call.get("function") or {}
                raw = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw)
                except ValueError:
                    args = {}
                blocks.append({"type": "tool_use", "id": call.get("id") or f"call_{len(blocks)}",
                               "name": fn.get("name", ""), "input": args})
            usage = data.get("usage") or {}
            return LLMResponse(
                content=blocks,
                stop_reason=str(choice.get("finish_reason", "stop")),
                input_tokens=int(usage.get("prompt_tokens", 0) or 0),
                output_tokens=int(usage.get("completion_tokens", 0) or 0),
                model=str(data.get("model", self.settings.model_name)),
                request_id=data.get("id"),
            )
        raise LLMError(f"模型调用失败：{last_error}")
