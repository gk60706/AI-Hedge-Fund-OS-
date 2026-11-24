"""User-defined OpenAI-compatible providers loaded from YAML."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from ai_team.adapters import (
    AdapterConfigError,
    AdapterRegistry,
    AdapterSpec,
    OpenAICompatibleAdapter,
    load_env_file,
)

DEFAULT_PROVIDERS_FILE = "configs/ai_providers.yaml"
_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


@dataclass(frozen=True, kw_only=True)
class ProviderConfig:
    provider_id: str
    display_name: str
    protocol: str = "openai"
    base_url: str
    model: str
    api_key_env: str = ""
    api_key: str = ""
    timeout: float = 120.0
    max_tokens: int = 4096
    temperature: float = 0.3
    enabled: bool = True
    tags: tuple = tuple()


def expand_env(value: Any, env: Mapping[str, str]) -> str:
    """Expand ${VAR} and ${VAR:-default}; unset VAR without default -> ""."""
    if value is None:
        return ""

    def _sub(match: re.Match) -> str:
        name, default = match.group(1), match.group(2)
        current = env.get(name, "")
        if current:
            return current
        return default if default is not None else ""

    return _ENV_PATTERN.sub(_sub, str(value)).strip()


def _number(pid: str, field: str, raw: Any, default: float, *, integer: bool = False) -> float:
    if raw is None:
        return default
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise AdapterConfigError(f"provider '{pid}': {field} must be a number, got {raw!r}")
    if integer:
        if isinstance(raw, float) and not raw.is_integer():
            raise AdapterConfigError(f"provider '{pid}': {field} must be an integer, got {raw!r}")
        return int(raw)
    return float(raw)


def _validate_numbers(pid: str, timeout: float, max_tokens: int, temperature: float) -> None:
    if timeout <= 0:
        raise AdapterConfigError(f"provider '{pid}': timeout must be > 0, got {timeout}")
    if not 1 <= max_tokens <= 32768:
        raise AdapterConfigError(f"provider '{pid}': max_tokens must be in [1, 32768], got {max_tokens}")
    if not 0 <= temperature <= 2:
        raise AdapterConfigError(f"provider '{pid}': temperature must be in [0, 2], got {temperature}")


def load_providers(path: str | Path, env: Mapping[str, str] | None = None) -> list[ProviderConfig]:
    env = dict(os.environ) if env is None else dict(env)
    file_path = Path(path)
    if not file_path.is_file():
        raise AdapterConfigError(f"providers file not found: {file_path}")
    try:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise AdapterConfigError(f"invalid YAML in {file_path}: {exc}") from exc
    if data is None:
        raise AdapterConfigError(f"providers file is empty: {file_path}")
    if not isinstance(data, dict):
        raise AdapterConfigError(f"{file_path}: top level must be a mapping with a 'providers' key")
    items = data.get("providers")
    if not isinstance(items, list):
        raise AdapterConfigError(f"{file_path}: 'providers' must be a list, got {type(items).__name__}")

    result: list[ProviderConfig] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AdapterConfigError(f"providers[{index}]: must be a mapping, got {type(item).__name__}")
        pid = str(item.get("provider_id") or "").strip()
        if not pid:
            raise AdapterConfigError(f"providers[{index}]: missing provider_id")
        if pid in seen:
            raise AdapterConfigError(f"provider '{pid}': duplicate provider_id")
        seen.add(pid)

        base_url = expand_env(item.get("base_url"), env)
        model = expand_env(item.get("model"), env)
        missing = [name for name, val in (("base_url", base_url), ("model", model)) if not val]
        if missing:
            raise AdapterConfigError(f"provider '{pid}': missing {', '.join(missing)}")

        timeout = _number(pid, "timeout", item.get("timeout"), 120.0)
        max_tokens = int(_number(pid, "max_tokens", item.get("max_tokens"), 4096, integer=True))
        temperature = _number(pid, "temperature", item.get("temperature"), 0.3)
        _validate_numbers(pid, timeout, max_tokens, temperature)

        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise AdapterConfigError(f"provider '{pid}': enabled must be true/false, got {enabled!r}")
        tags_raw = item.get("tags") or ()
        if isinstance(tags_raw, str):
            tags_raw = (tags_raw,)
        if not isinstance(tags_raw, (list, tuple)):
            raise AdapterConfigError(f"provider '{pid}': tags must be a list")

        result.append(
            ProviderConfig(
                provider_id=pid,
                display_name=str(item.get("display_name") or pid),
                protocol=str(item.get("protocol") or "openai").strip().lower(),
                base_url=base_url,
                model=model,
                api_key_env=expand_env(item.get("api_key_env"), env) or f"AIH_{pid.upper()}_API_KEY",
                api_key=expand_env(item.get("api_key"), env),
                timeout=timeout,
                max_tokens=max_tokens,
                temperature=temperature,
                enabled=enabled,
                tags=tuple(str(t) for t in tags_raw),
            )
        )
    return result


def build_custom_registry(
    path: str | Path,
    env: Mapping[str, str] | None = None,
    *,
    transport: Any = None,
    timeout: float | None = None,
) -> AdapterRegistry:
    env = dict(os.environ) if env is None else dict(env)
    adapters: dict[str, OpenAICompatibleAdapter] = {}
    skipped: dict[str, str] = {}
    for cfg in load_providers(path, env):
        if not cfg.enabled:
            continue
        if cfg.protocol != "openai":
            skipped[cfg.provider_id] = f"unsupported protocol: {cfg.protocol} (only 'openai')"
            continue
        api_key = cfg.api_key or env.get(cfg.api_key_env, "")
        if not api_key:
            skipped[cfg.provider_id] = f"missing: {cfg.api_key_env}"
            continue
        prefix = f"AIH_{cfg.provider_id.upper()}"
        spec = AdapterSpec(
            agent_id=cfg.provider_id,
            display_name=cfg.display_name,
            api_key_env=cfg.api_key_env,
            base_url_env=f"{prefix}_BASE_URL",
            model_env=f"{prefix}_MODEL",
            default_base_url=cfg.base_url,
            default_model=cfg.model,
            notes="custom provider (YAML)",
        )
        try:
            effective_timeout = cfg.timeout if timeout is None else float(timeout)
            _validate_numbers(cfg.provider_id, effective_timeout, cfg.max_tokens, cfg.temperature)
            adapters[cfg.provider_id] = OpenAICompatibleAdapter(
                spec,
                api_key,
                cfg.base_url,
                cfg.model,
                timeout=effective_timeout,
                max_tokens=cfg.max_tokens,
                temperature=cfg.temperature,
                transport=transport,
            )
        except AdapterConfigError as exc:
            skipped[cfg.provider_id] = f"config error: {exc}"
    return AdapterRegistry(adapters, skipped)


def describe_providers(registry: AdapterRegistry, providers: list[ProviderConfig]) -> list[dict]:
    available = set(getattr(registry, "adapters", {}) or {})
    skipped = dict(getattr(registry, "skipped", {}) or {})
    rows: list[dict] = []
    for cfg in providers:
        if cfg.provider_id in available:
            status = "available"
        elif cfg.provider_id in skipped:
            status = f"skipped: {skipped[cfg.provider_id]}"
        elif not cfg.enabled:
            status = "skipped: disabled"
        else:
            status = "skipped: unknown"
        rows.append(
            {
                "provider_id": cfg.provider_id,
                "display_name": cfg.display_name,
                "base_url": cfg.base_url,
                "model": cfg.model,
                "tags": list(cfg.tags),
                "status": status,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai_team.providers", description="Custom OpenAI-compatible providers")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("list", "print providers as JSON"), ("check", "offline config check")):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("--file", default=DEFAULT_PROVIDERS_FILE)
    args = parser.parse_args(argv)

    try:
        load_env_file()
    except Exception:  # .env is optional
        pass
    env = dict(os.environ)

    try:
        providers = load_providers(args.file, env)
        registry = build_custom_registry(args.file, env)
    except AdapterConfigError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2

    rows = describe_providers(registry, providers)
    if args.command == "list":
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    ok = 0
    for row in rows:
        if row["status"] == "available":
            print(f"OK {row['provider_id']} {row['model']}")
            ok += 1
        else:
            print(f"SKIP {row['provider_id']} {row['status']}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
