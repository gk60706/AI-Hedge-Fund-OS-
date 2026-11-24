"""
AI Hedge Fund OS
V3.10 - Multi-AI Collaboration Engine

Main Entry Point

研究流程：

    Team Config
      ↓
    Task Assignment
      ↓
    Multi-Agent Reports
      ↓
    Cross Validation
      ↓
    Debate
      ↓
    Consensus
      ↓
    Investment Committee
      ↓
    decision.json

用法：

    # 用现成的三份报告 + 辩论 + 投票跑一次完整链路
    python main_v310.py \\
        --symbol 300394 \\
        --reports-dir research\\300394_2026-11-16\\reports \\
        --debate research\\300394_2026-11-16\\debate.json \\
        --ballots research\\300394_2026-11-16\\ballots.json \\
        --output research\\300394_2026-11-16\\decision.json \\
        --project-root research\\300394_2026-11-16

    # 显示完整参数
    python main_v310.py --help

注意：本入口只做研究与治理，不产生任何实盘交易指令。
"""

from __future__ import annotations

import sys
from typing import Sequence

from ai_team.research_pipeline import main as pipeline_main


def main(argv: Sequence[str] | None = None) -> int:
    """V3.10 统一入口：转交给 ai_team.research_pipeline 的命令行实现。"""
    return pipeline_main(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
