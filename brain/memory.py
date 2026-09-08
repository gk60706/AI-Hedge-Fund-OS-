"""AI 长期记忆系统 (V0.9)

基于 ChromaDB 存储与检索投资记忆。
"""
import chromadb

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
