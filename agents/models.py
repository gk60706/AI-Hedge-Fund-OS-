"""V0.2：所有 Agent 输出统一格式。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    agent: str
    score: float = Field(ge=0, le=100)
    opinion: str
    risks: list[str] = Field(default_factory=list)


class InvestmentDecision(BaseModel):
    stock: str
    score: float
    action: str  # BUY / HOLD / AVOID
    position: float
    reason: str
