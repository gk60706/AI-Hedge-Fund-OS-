"""新闻分析 Agent (V0.9)

调用 LLM 分析 A 股新闻：利好行业、利空风险、对股票影响。
"""
from brain.llm_agent import ask_ai


def news_analysis(news: str) -> str:
    """分析 A 股新闻。

    :param news: 新闻文本
    :return: LLM 分析结果
    """
    prompt = f"""分析下面A股新闻：
{news}
输出：
1. 利好行业
2. 利空风险
3. 对股票影响
"""
    result = ask_ai(prompt)
    return result
