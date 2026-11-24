"""V1.0 晚间复盘：生成每日 AI 交易复盘。

V2.2 追加：EveningReport（每日晚报生成器）。
"""


def evening_report(trades):
    return f"""

# AI交易复盘

交易: {trades}
AI总结: 优化下一交易日策略

"""


# ---------------------------------------------------------------------------
# V2.2 每日 AI 晚报生成。
# ---------------------------------------------------------------------------
class EveningReport:
    """V2.2 每日 AI 晚报生成器。"""

    def generate(self, trades, performance) -> str:
        """生成晚报文本。

        Args:
            trades: 当日交易。
            performance: 收益表现。

        Returns:
            晚报 Markdown 文本。
        """
        return f"""

# AI基金每日复盘


交易:
{trades}
收益:
{performance}
AI总结:

优化下一交易日策略


"""
