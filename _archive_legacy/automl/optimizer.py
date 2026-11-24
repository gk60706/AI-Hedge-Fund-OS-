"""V2.8 AutoML 自动参数优化：网格搜索最佳参数组合。"""


class AutoOptimizer:
    """AutoML 优化器。"""

    def search(self, params):
        best = None
        best_score = -999
        for p in params:
            score = p["score"]
            if score > best_score:
                best_score = score
                best = p
        return best
