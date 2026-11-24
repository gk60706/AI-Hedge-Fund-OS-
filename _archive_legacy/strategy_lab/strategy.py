"""V2.8/V2.8.1 策略基因与策略对象。

V2.8 版：Strategy（genes dict 框架演示版）
V2.8.1 版：StrategyDNA dataclass + StrategyV281（可运行闭环版，类名后缀保留旧接口）
"""
from dataclasses import dataclass, asdict
import random


class Strategy:
    """V2.8 框架演示版：策略 DNA 为 dict，支持变异。"""

    def __init__(self, genes):
        self.genes = genes
        self.performance = {}

    def mutate(self):
        import random
        key = random.choice(list(self.genes.keys()))
        self.genes[key] = round(random.random(), 2)
        return self


@dataclass
class StrategyDNA:
    """V2.8.1 策略 DNA：真正的策略基因（9 个基因位）。"""

    momentum_weight: float
    value_weight: float
    capital_weight: float
    volume_weight: float
    buy_threshold: float
    stop_loss: float
    take_profit: float
    holding_period: int
    max_position: float

    def to_dict(self):
        return asdict(self)


class StrategyV281:
    """V2.8.1 可运行版策略：携带 DNA + 回测指标 + 生命周期状态。"""

    def __init__(self, dna: StrategyDNA):
        self.dna = dna
        self.metrics = {}
        self.status = "EXPERIMENT"

    def mutate(self):
        dna = self.dna
        genes = [
            "momentum_weight", "value_weight", "capital_weight",
            "volume_weight", "buy_threshold", "stop_loss",
            "take_profit", "holding_period", "max_position",
        ]
        gene = random.choice(genes)
        if gene == "holding_period":
            dna.holding_period = random.randint(5, 60)
        elif gene == "max_position":
            dna.max_position = random.uniform(0.05, 0.30)
        elif gene == "stop_loss":
            dna.stop_loss = random.uniform(0.03, 0.15)
        elif gene == "take_profit":
            dna.take_profit = random.uniform(0.05, 0.40)
        else:
            current = getattr(dna, gene)
            noise = random.uniform(-0.15, 0.15)
            setattr(dna, gene, max(0, min(1, current + noise)))
        return self
