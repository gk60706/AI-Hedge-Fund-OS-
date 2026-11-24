"""V1.1 AI 投资记忆系统：检索历史经验。"""
from rag.vector_store import search


def recall_memory(question):
    result = search(question)
    return result["documents"]
