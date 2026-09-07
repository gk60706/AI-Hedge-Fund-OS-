from __future__ import annotations

from backend.config import Settings, get_settings


def test_settings_defaults():
    settings = Settings()
    assert settings.app_name == "AI Hedge Fund OS"
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.openai_model == "gpt-5"
    assert settings.openai_api_key == ""


def test_get_settings_reads_env(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.5")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = get_settings()
    assert settings.openai_api_key == "sk-test-123"
    assert settings.openai_model == "gpt-5.5"
    assert settings.log_level == "DEBUG"
    get_settings.cache_clear()
