from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AlphaGenome:
    formula: str
    score: float = 0.0
    ic: float = 0.0
    icir: float = 0.0
    oos_score: float = 0.0
    complexity: int = 0
    generation: int = 0
    status: str = "EXPERIMENT"

    def fitness(self):
        return (
            self.oos_score * 0.5
            + self.ic * 0.2
            + self.icir * 0.2
            - self.complexity * 0.01
        )
