"""LLM 核心接口 (V0.9)

统一封装 OpenAI Responses API（非 chat.completions）。
API Key 只从 config.settings 读取（来自 .env），客户端惰性初始化，
无 Key 时模块可正常导入，仅真正调用时才会报错。
"""
from openai import OpenAI

from config.settings import OPENAI_API_KEY

SYSTEM_PROMPT = """你是一名专业量化基金经理。
负责A股投资分析。"""

_client = None


def get_client() -> OpenAI:
    """惰性创建 OpenAI 客户端（API Key 来自 .env）。"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def ask_ai(prompt: str) -> str:
    """调用 OpenAI Responses API 完成分析任务。

    :param prompt: 用户输入
    :return: 模型输出文本
    """
    response = get_client().responses.create(
        model="gpt-5",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return response.output_text
