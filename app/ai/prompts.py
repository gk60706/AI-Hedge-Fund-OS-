"""AI 研究提示词模板。"""
from __future__ import annotations

RESEARCH_SYSTEM_PROMPT = """\
你是一名严谨的 A 股量化研究员，擅长基于真实行情数据撰写结构化、可读的中文研究报告。

写作要求：
1. 只基于用户提供的行情数据与公司信息进行论述，不得编造数据；
2. 结论与风险提示分开陈述；
3. 语言专业、克制，不承诺收益，不构成投资建议；
4. 使用 Markdown 标题与列表组织内容。
"""


def build_research_prompt(symbol: str, focus: str, market_summary: str, company_info: str) -> str:
    """组装研究报告生成提示词。"""
    return f"""\
请针对 A 股股票 {symbol} 撰写一份简短的研究报告。

研究重点：{focus or "综合"}

===== 行情数据摘要 =====
{market_summary or "（无可用行情数据）"}

===== 公司信息 =====
{company_info or "（无可用公司信息）"}

请输出 Markdown 格式报告，包含：一、行情概览；二、技术面观察；三、风险提示。
"""


def build_market_summary(rows: list[dict]) -> str:
    """将历史行情记录转换为给模型的 CSV 风格文本摘要。"""
    if not rows:
        return "（无数据）"
    lines = ["日期,开盘,收盘,最高,最低,成交量,成交额,涨跌幅(%)"]
    for r in rows[:60]:
        pct = r.get("pct_change")
        lines.append(
            f"{r['date']},{float(r['open']):.2f},{float(r['close']):.2f},"
            f"{float(r['high']):.2f},{float(r['low']):.2f},{int(r['volume'])},"
            f"{float(r['amount']):.0f},{pct if pct is not None else ''}"
        )
    return "\n".join(lines)
