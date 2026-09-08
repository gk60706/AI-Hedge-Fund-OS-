"""全局配置 (V0.9)

所有 API Key 只从环境变量读取（由 .env 经 python-dotenv 加载），不硬编码。
"""
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-5"
