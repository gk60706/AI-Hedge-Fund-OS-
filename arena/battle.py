"""V1.3 策略竞技场：让多个投资经理对同一标的竞争打分。"""


class StrategyArena:
    """策略竞技场。"""

    def __init__(self, managers: list) -> None:
        self.managers = managers

    def compete(self, stock: dict) -> list:
        """让全部投资经理对 stock 出牌，返回结果列表。"""
        results = []
        for manager in self.managers:
            result = manager.analyze(stock)
            results.append(result)
        return results
