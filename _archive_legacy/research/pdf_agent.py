"""V2.1 财报 PDF 阅读 Agent：自动读取上市公司财报 PDF。"""

from pypdf import PdfReader


class PDFResearchAgent:
    """财报 PDF 阅读 Agent（研究/模拟用途）。"""

    def read(self, path: str) -> str:
        """读取 PDF 全文。

        Args:
            path: PDF 文件路径。

        Returns:
            提取的文本。
        """
        reader = PdfReader(path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text

    def summarize(self, text: str) -> dict:
        """总结财报要点（模拟占位，真实分析待接入 LLM）。

        Args:
            text: 财报文本。

        Returns:
            摘要字典。
        """
        return {
            "business": "公司主营业务分析",
            "growth": "收入利润趋势",
            "risk": "主要风险",
        }
