from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class ExperimentStore:
    def __init__(
        self,
        path="experiments/results",
    ):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True,)

    def save(
        self,
        name: str,
        result: dict,
    ):
        timestamp = (
            datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        file = (
            self.path
            / f"{name}_{timestamp}.json"
        )
        file.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        return str(file)
