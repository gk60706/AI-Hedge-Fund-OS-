"""V0.2：OpenAI Responses API 统一调用。"""
from __future__ import annotations

from openai import OpenAI

from backend.config import settings


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY 未配置。请复制 .env.example 为 .env 并填写新的 API Key。"
        )
    return OpenAI(api_key=settings.openai_api_key)


def ask_ai(prompt: str) -> str:
    """调用 OpenAI Responses API；gpt-5 系列不支持 temperature 参数，故不传。"""
    response = _client().responses.create(
        model=settings.openai_model,
        input=prompt,
    )
    return response.output_text
