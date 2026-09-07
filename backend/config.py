from __future__ import annotations

import os
import sys
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


def _enable_system_proxy_if_needed() -> None:
    """Windows 下若未显式设置代理环境变量，自动继承系统代理（Clash 等）。

    仅用于让 OpenAI API 可达；不影响 API Key 的读取（仍只来自 .env）。
    可用 AUTO_SYSTEM_PROXY=0 关闭该行为。
    """
    if os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("ALL_PROXY"):
        return
    if os.getenv("AUTO_SYSTEM_PROXY", "1").strip().lower() in ("0", "false", "no"):
        return
    if sys.platform != "win32":
        return
    try:
        import winreg

        key_path = (
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        )
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
        if not enabled or not server:
            return
        if "=" in server:  # 形如 "http=127.0.0.1:7897;https=..." 时取 https 段
            for part in server.split(";"):
                if part.lower().startswith("https="):
                    server = part.split("=", 1)[1]
                    break
            else:
                return
        if not server.startswith(("http://", "https://")):
            server = f"http://{server}"
        os.environ.setdefault("HTTPS_PROXY", server)
        os.environ.setdefault("HTTP_PROXY", server)
    except Exception:
        # 读取系统代理失败时静默跳过，不阻塞程序启动
        pass


_enable_system_proxy_if_needed()


class Settings(BaseModel):
    app_name: str = Field(default="AI Hedge Fund OS")
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-5")


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "AI Hedge Fund OS"),
        app_env=os.getenv("APP_ENV", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5"),
    )
