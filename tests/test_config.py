"""配置模块测试。"""
from __future__ import annotations

from app.core.config import Settings, get_settings


def test_settings_defaults():
    settings = get_settings()
    assert settings.app_name == "AI Hedge Fund OS"
    assert settings.app_version == "0.1.0"
    assert settings.openai_model == "gpt-4o-mini"


def test_settings_reads_env_vars(monkeypatch):
    """OpenAI Key 等敏感配置只能来自环境变量/.env，且可被环境变量覆盖。"""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")

    settings = Settings()
    assert settings.openai_api_key == "sk-test-123"
    assert settings.openai_model == "gpt-4o"


def test_settings_default_key_empty():
    """未配置任何密钥时默认必须为空，避免密钥硬编码。"""
    settings = Settings(_env_file=None)
    assert settings.openai_api_key == ""
