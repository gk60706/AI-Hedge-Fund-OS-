"""AI 每日复盘 (V0.9)

根据当日交易记录调用 LLM 生成复盘报告。
"""
from brain.llm_agent import ask_ai


def daily_review(trades: str) -> str:
    """生成每日复盘。

    :param trades: 当日交易记录
    :return: LLM 复盘报告
    """
    prompt = f"""今天交易记录:
{trades}
请生成：
## 今日收益
## 成功交易
## 错误交易
## 明日策略调整
"""
    return ask_ai(prompt)
