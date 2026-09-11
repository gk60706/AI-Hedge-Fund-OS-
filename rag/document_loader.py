"""V1.1 PDF 财报读取 Agent：从 PDF 提取文本。

V2.1 追加：DocumentLoader（RAG 知识库：读取文件夹内 .txt 文档）。
"""
from pypdf import PdfReader


def load_pdf(path):
    reader = PdfReader(path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text


# ---------------------------------------------------------------------------
# V2.1 RAG 知识库：读取文件夹内全部 .txt 文档。
# ---------------------------------------------------------------------------
import os


class DocumentLoader:
    """RAG 文档加载器：读取文件夹内全部 .txt 文件。"""

    def load_folder(self, folder: str) -> list:
        """遍历 folder，返回所有 .txt 文件的全文列表。"""
        docs = []
        for file in os.listdir(folder):
            if file.endswith(".txt"):
                with open(folder + "/" + file, encoding="utf-8") as f:
                    docs.append(f.read())
        return docs
