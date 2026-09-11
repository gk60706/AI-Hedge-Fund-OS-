"""V2.1 新闻舆情 Agent：对新闻做情感统计。"""


class NewsAgent:
    """新闻舆情分析 Agent。"""

    def analyze(self, news: list) -> dict:
        """统计正面/负面新闻占比。

        Args:
            news: 含 sentiment 字段（"positive" 或其他）的新闻列表。

        Returns:
            {"sentiment_score": float}
        """
        positive = 0
        negative = 0
        for item in news:
            if item["sentiment"] == "positive":
                positive += 1
            else:
                negative += 1
        score = (positive / (positive + negative + 1))
        return {"sentiment_score": score}
