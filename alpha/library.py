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
# ============================================================================
# V3.9.1 unified research engine - alpha library (directory based, dump)
# ============================================================================


class AlphaLibraryV391:
    def __init__(self, root=Path("alpha_library")):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "alphas.json"

    def save(self, records: list[dict]):
        serializable = []
        for record in records:
            item = {}
            for key, value in record.items():
                if key in {"expression", "signal", "ic_series"}:
                    continue
                item[key] = value
            if "expression" in record:
                item["expression"] = record["expression"].to_string()
            serializable.append(item)
        self.path.write_text(
            json.dumps(serializable, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def load(self):
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def top(self, n: int = 20):
        return self.load()[:n]


import json  # noqa: E402
from pathlib import Path  # noqa: E402
