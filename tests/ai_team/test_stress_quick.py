"""CI 用的快速压测：连续跑 3 次 V3.10 研究链路。

完整 20 次压测（含 evolution 断点续跑）请运行：
    python scripts/stress_v310_e2e.py --iterations 20
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "stress_v310_e2e.py"


def test_three_iteration_pipeline_stress(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--iterations",
            "3",
            "--skip-evolution",
            "--workdir",
            str(tmp_path / "stress"),
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "3/3 passed" in result.stdout
