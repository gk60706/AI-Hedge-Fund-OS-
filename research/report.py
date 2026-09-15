# -*- coding: utf-8 -*-
"""V3.9.1 research report writer (dump verbatim)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def write_report(result, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = []
    content.append("# AI Hedge Fund OS V3.9.1 Research Report")
    content.append("")
    content.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    content.append("")
    content.append("## Champion Alpha")
    content.append("")
    content.append("```json")
    content.append(
        json.dumps(result.champion, ensure_ascii=False, indent=2, default=str)
    )
    content.append("```")
    content.append("")
    content.append("## Data Audit")
    content.append("")
    content.append("```json")
    content.append(
        json.dumps(result.audit, ensure_ascii=False, indent=2, default=str)
    )
    content.append("```")
    content.append("")
    content.append("## Backtest Metrics")
    content.append("")
    content.append("```json")
    content.append(
        json.dumps(result.backtest_metrics, ensure_ascii=False, indent=2, default=str)
    )
    content.append("```")
    content.append("")
    content.append("## Top Alpha Candidates")
    content.append("")
    for index, candidate in enumerate(result.candidates, start=1):
        expression = candidate["expression"].to_string()
        content.append(
            f"{index}. `{expression}` "
            f"| IC={candidate['ic']:.6f} "
            f"| OOS IC={candidate['oos_ic']:.6f} "
            f"| Score={candidate['robust_score']:.4f}"
        )
    content.append("")
    content.append("> 本报告仅用于量化研究、回测和模拟。")
    content.append("> 不构成投资建议，也不代表未来收益。")
    path.write_text(chr(10).join(content), encoding="utf-8")
    return path
