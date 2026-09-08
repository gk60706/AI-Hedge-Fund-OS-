"""V1.1 投资知识向量库：基于 ChromaDB 的长期记忆存储。

Python 3.14 无 chroma-hnswlib 预编译 wheel 时，自动降级为本地 JSON 向量库
（模块接口 add_document / search 保持不变）。
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
    client = chromadb.PersistentClient(path=str(_MEMORY_DIR))
    collection = client.get_or_create_collection("investment_memory")

    def add_document(text):
        collection.add(
            documents=[text],
            ids=[str(hash(text))],
        )

    def search(query):
        return collection.query(
            query_texts=[query],
            n_results=5,
        )

else:
    _FALLBACK_FILE = _MEMORY_DIR / "investment_knowledge.json"

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

    def add_document(text):
        """添加一条知识（降级实现）。"""
        items = _load()
        _save(items + [text])

    def search(query):
        """检索知识（降级实现：返回最近 5 条）。"""
        items = _load()
        return {"documents": [items[-5:]] if items else [[]]}
