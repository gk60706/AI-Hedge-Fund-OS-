"""V2.9 AI 多 Agent 投资委员会：Agent 基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    name = "base_agent"

    @abstractmethod
    def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Agent 独立分析。
        """
        raise NotImplementedError

    def normalize_score(self, score: float) -> float:
        return max(0.0, min(100.0, float(score)))
