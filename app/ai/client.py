"""OpenAI Responses API 客户端封装。

所有密钥只从 .env 读取（见 app.core.config.Settings），禁止硬编码。
"""
from __future__ import annotations

from typing import Any

from openai import OpenAI

from app.core.config import get_settings


class OpenAIClient:
    """基于 OpenAI Responses API 的文本生成客户端。"""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置：请在项目根目录的 .env 中设置后重试")
        self._settings = settings
        self._client = OpenAI(api_key=settings.openai_api_key)

    @property
    def model(self) -> str:
        return self._settings.openai_model

    def complete(self, *, prompt: str, system: str | None = None, temperature: float = 0.3) -> str:
        """调用 OpenAI Responses API 生成文本并返回纯文本结果。"""
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._client.responses.create(
            model=self.model,
            input=messages,
            temperature=temperature,
        )
        return response.output_text
