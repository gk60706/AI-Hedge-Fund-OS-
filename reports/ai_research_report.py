"""V2.1 AI 研报生成 Agent：生成 AI 投资研究报告。"""


class ResearchReportGenerator:
    """AI 投资研究报告生成器。"""

    def generate(self, company, financial, news) -> str:
        """生成研报文本。

        Args:
            company: 公司信息。
            financial: 财务分析。
            news: 新闻舆情。

        Returns:
            研报 Markdown 文本。
        """
        report = f"""

# AI投资研究报告


## 公司
{company}
## 财务分析
{financial}
## 新闻舆情
{news}
## AI投资观点

综合评分:

BUY / HOLD / SELL


"""
        return report
