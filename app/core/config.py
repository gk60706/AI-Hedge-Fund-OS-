"""应用配置。

安全约定：所有敏感配置（API Key 等）只能通过项目根目录的 .env 读取，
禁止硬编码进代码，禁止提交到 GitHub（见 .gitignore）。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（app/core/config.py -> 项目根）
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """全局配置。字段名与 .env 中的键一一对应。"""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- 应用 ----
    app_name: str = "AI Hedge Fund OS"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # ---- OpenAI（仅从 .env 读取）----
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # ---- 报告输出目录 ----
    report_dir: Path = BASE_DIR / "reports"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取全局唯一配置实例（带缓存）。"""
    return Settings()
