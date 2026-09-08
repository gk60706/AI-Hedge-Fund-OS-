"""V1.1 投资知识向量库：基于 ChromaDB 的长期记忆存储。"""
import chromadb

client = chromadb.PersistentClient(path="./memory")
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
