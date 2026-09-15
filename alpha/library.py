from __future__ import annotations

import json
from pathlib import Path


class AlphaLibrary:
    def __init__(self, path="alpha_library.json"):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return []
        return json.loads(
            self.path.read_text(encoding="utf-8")
        )

    def save(self, alpha):
        library = self.load()
        library.append(alpha)
        self.path.write_text(
            json.dumps(
                library,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def top(self, n=20):
        library = self.load()
        library.sort(
            key=lambda x: x.get(
                "oos_score",
                x.get("adjusted_score", 0),
            ),
            reverse=True,
        )
        return library[:n]
