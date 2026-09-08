"""AI 长期记忆系统 (V0.9)

基于 ChromaDB 存储与检索投资记忆。
Python 3.14 无 chroma-hnswlib 预编译 wheel 时，自动降级为本地 JSON 记忆库
（模块接口 save_memory / search_memory 保持不变）。
"""
import json
import os
from pathlib import Path

_MEMORY_DIR = Path(os.environ.get("AIHF_MEMORY_DIR", "memory"))
_MEMORY_DIR.mkdir(parents=True, exist_ok=True)

try:
    import chromadb  # type: ignore

    _HAS_CHROMADB = True
except ImportError:  # pragma: no cover - 依赖缺失时走降级
    _HAS_CHROMADB = False

if _HAS_CHROMADB:
    client = chromadb.Client()
    collection = client.create_collection("investment_memory")

    def save_memory(text: str) -> None:
        """保存一条投资记忆。"""
        collection.add(
            documents=[text],
            ids=[str(hash(text))],
        )

    def search_memory(query: str):
        """检索投资记忆（返回 top-3）。"""
        return collection.query(
            query_texts=[query],
            n_results=3,
        )

else:
    _FALLBACK_FILE = _MEMORY_DIR / "investment_memory.json"

    def _load() -> list:
        if _FALLBACK_FILE.exists():
            try:
                return json.loads(_FALLBACK_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _save(items: list) -> None:
        _FALLBACK_FILE.write_text(
            json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def save_memory(text: str) -> None:
        """保存一条投资记忆（降级实现）。"""
        items = _load()
        _save(items + [text])

    def search_memory(query: str):
        """检索投资记忆（降级实现：返回最近 3 条）。"""
        items = _load()
        return {"documents": [items[-3:]] if items else [[]]}
