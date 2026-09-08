"""V1.1 PDF 财报读取 Agent：从 PDF 提取文本。"""
from pypdf import PdfReader


def load_pdf(path):
    reader = PdfReader(path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text
