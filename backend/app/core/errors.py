"""统一错误：API 只返回 {"error": {"code", "message"}}，不泄露堆栈。"""
from __future__ import annotations


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class LLMError(AppError):
    def __init__(self, message: str, code: str = "MODEL_ERROR") -> None:
        super().__init__(code, message, 502)
