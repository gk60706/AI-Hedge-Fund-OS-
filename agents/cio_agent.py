from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from backend.config import get_settings

SYSTEM_PROMPT = """
你是 AI Hedge Fund OS 的首席投资官（CIO）。

你的任务是基于用户提供的 A 股行情快照，
生成研究用途的股票分析。

严禁把缺失的数据当成事实。

不要虚构：

- 财务数据
- 新闻
- 估值
- 机构持仓
- 公司公告

输出必须包含：

1. 公司/股票基本判断
2. 行情结构
3. 行业与业务逻辑
4. 多空因素
5. 风险
6. 后续需要补充的数据
7. 研究结论

如果数据不足：

明确写：

"需要进一步研究"

这是研究辅助系统，
不是个性化投资建议。
"""


def _client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY 未配置。"
            "请复制 .env.example 为 .env "
            "并填写新的 API Key。"
        )
    return OpenAI(api_key=settings.openai_api_key)


def generate_cio_report(market_data: dict[str, Any]) -> str:
    settings = get_settings()
    prompt = (
        "请分析以下 A 股行情快照，"
        "并严格区分事实与推断。\n\n"
        + json.dumps(market_data, ensure_ascii=False, indent=2)
    )
    response = _client().responses.create(
        model=settings.openai_model,
        instructions=SYSTEM_PROMPT,
        input=prompt,
        max_output_tokens=3000,
    )
    return response.output_text.strip()
