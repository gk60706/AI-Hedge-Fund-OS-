"""V3.0.5 AI Trade Review Agent：接入 OpenAI 生成交易复盘。

API Key 只从 .env 读取（backend.config.get_settings）。
"""
from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from backend.config import get_settings


class TradeReviewAgent:
    def __init__(self):
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置")
        self.client = OpenAI(
            api_key=settings.openai_api_key
        )
        self.model = settings.openai_model

    def review(self, trade: dict[str, Any]) -> str:
        prompt = f"""
你是AI量化基金的交易复盘经理。

请分析下面这笔交易：
{json.dumps(
    trade,
    ensure_ascii=False,
    indent=2,
    default=str,
)}
请回答：

1. 为什么这笔交易可能成功/失败
2. 买入时机是否合理
3. 仓位是否合理
4. 风险控制是否合理
5. 是否存在追涨、抄底、过度交易等问题
6. 下次策略应该如何改进

严格区分事实与推断。
不要虚构没有提供的数据。
"""
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
        )
        return response.output_text
