"""AI CIO 基金经理 (V0.9)

综合市场、个股、新闻，调用 LLM 输出投资决策。
"""
from brain.llm_agent import ask_ai


def cio_decision(market, stock, news) -> str:
    """AI 基金经理决策。

    :param market: 市场环境描述
    :param stock: 股票信息
    :param news: 新闻信息
    :return: LLM 决策文本（是否买入/建议仓位/风险/投资逻辑）
    """
    prompt = f"""你现在是AI基金经理。

市场:
{market}
股票:
{stock}
新闻:
{news}
请输出：
1. 是否买入
2. 建议仓位
3. 风险
4. 投资逻辑
"""
    return ask_ai(prompt)
