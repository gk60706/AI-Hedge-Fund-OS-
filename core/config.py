"""V1.0 核心配置：所有 API Key 只从 .env 读取。

- 复用 backend.config 的代理自动识别能力
- 提供 get_openai_client()：按 .env 的 OPENAI_API_KEY / OPENAI_MODEL 构造 OpenAI 客户端
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _enable_system_proxy_if_needed() -> None:
    """Windows 下若未显式设置代理环境变量，自动继承系统代理（Clash 等）。"""
    if os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("ALL_PROXY"):
        return
    if os.getenv("AUTO_SYSTEM_PROXY", "1").strip().lower() in ("0", "false", "no"):
        return
    if sys.platform != "win32":
        return
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
        if not enabled or not server:
            return
        if "=" in server:
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
        pass


_enable_system_proxy_if_needed()


@lru_cache
def get_openai_api_key() -> str:
    return os.getenv("OPENAI_API_KEY", "")


@lru_cache
def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5")


@lru_cache
def get_openai_client():
    """构造 OpenAI 客户端（OpenAI Responses API）。Key 只来自 .env。"""
    from openai import OpenAI

    return OpenAI(api_key=get_openai_api_key() or None)
