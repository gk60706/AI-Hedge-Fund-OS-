"""V1.2 AI 代码生成 Agent：调用 OpenAI Responses API 生成量化策略代码。

API Key 只从 .env 读取（经 backend.config.get_settings），
统一使用 OpenAI Responses API（不使用 chat.completions）。
"""

from openai import OpenAI

from backend.config import get_settings


def _client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY 未配置。"
            "请复制 .env.example 为 .env 并填写新的 API Key。"
        )
    return OpenAI(api_key=settings.openai_api_key)


def generate_code(strategy: dict) -> str:
    """根据策略描述生成 Python 量化回测代码。

    :param strategy: 策略 dict（含 name/entry/exit/position 等字段）
    :return: 生成的策略代码文本
    """
    settings = get_settings()
    prompt = f"""
你是一名量化开发工程师。

根据策略：
{strategy}
生成Python量化交易代码。

要求：
1. pandas
2. numpy
3. 支持回测
4. 返回收益率
"""
    response = _client().responses.create(
        model=settings.openai_model,
        input=prompt,
        max_output_tokens=3000,
    )
    return response.output_text.strip()
