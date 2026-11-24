"""V0.4 PDF 财报读取 Agent。"""
from __future__ import annotations

from pypdf import PdfReader


def read_pdf(filepath: str) -> str:
    reader = PdfReader(filepath)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def summarize_report(text: str) -> dict:
    keywords = ["人工智能", "订单", "增长", "利润", "研发"]
    return {
        "length": len(text),
        "keywords": [x for x in keywords if x in text],
    }
