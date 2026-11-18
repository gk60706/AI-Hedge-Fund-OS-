"""
AI Hedge Fund OS V3.10 - 多 AI API 适配器

把三个 AI 助手（ChatGPT / Grok / Hark）从「人工抄报告」变成可编程调用。

设计约束：

1. 只用标准库（``urllib`` + ``json``），不给 ``ai_team`` 增加第三方依赖；
2. 网络出口可注入（``transport``），测试完全不联网；
3. 缺 key / 缺 base_url / 缺 model 时不发请求，登记为 skipped 并给出原因；
4. 任何密钥都不写日志、不写产物、不进异常消息；
5. 报告正文严格按 ``report_collector.DEFAULT_REQUIRED_SECTIONS`` 的 7 个英文小节输出，
   否则收集阶段会整份拒收。

本模块只负责「取回文本」，不做辩论、不做投票，也不产生任何交易指令。
"""

from __future__ import annotations

import email.utils
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ai_team.source_extraction import extract_sources_from_content

# ============================================================
# 常量
# ============================================================

#: 与 ``ai_team.config.AgentRole`` 对应的角色名，用于取角色提示词
AGENT_ROLE_NAMES = {
    "chatgpt": "CIO",
    "grok": "INTELLIGENCE",
    "hark": "ANALYST",
}

#: 报告必须命中的小节（与 report_collector 保持一致，测试里做交叉校验）
REQUIRED_SECTIONS = (
    "Executive Summary",
    "Key Findings",
    "Evidence and Sources",
    "Analytical Reasoning",
    "Risks and Limitations",
    "Independent Conclusion",
    "Confidence Level",
)

SYSTEM_PROMPT = (
    "You are one member of a multi-AI investment research team. "
    "You must be independent, mark unverified data as unverified, "
    "never fabricate figures, never give trade instructions, "
    "and always answer in the required section format."
)

REPORT_CONTRACT = """

==================================================
OUTPUT CONTRACT (MANDATORY)

Return exactly one Markdown report. Its headings must be, in this order and
spelled exactly like this (Markdown heading level 2 or 3, one per line):

## Executive Summary
## Key Findings
## Evidence and Sources
## Analytical Reasoning
## Risks and Limitations
## Independent Conclusion
## Confidence Level

Rules:

1. Keep the whole report under 900 words.
2. Every number must carry its source and reporting period. Anything you could
   not verify must be written as "unverified".
3. "Analytical Reasoning" must show how the conclusion follows from the
   findings, and state at least one piece of counter-evidence.
4. Under "## Confidence Level", print a single number between 0.00 and 1.00,
   followed by one sentence explaining why (for example: "0.72 - cash-flow
   confirmation is missing").
5. Do not output any section outside the list above, and do not add a title
   before the first heading.
6. Never include buy/sell instructions, position sizes, or order details.
"""


# ============================================================
# 异常
# ============================================================


class AdapterError(Exception):
    """适配器相关错误的基类。"""


class AdapterConfigError(AdapterError):
    """缺少配置（key / base_url / model）。"""


class AdapterUnavailableError(AdapterError):
    """该助手没有可用的调用通道（例如 Hark 无公开 API）。"""


class AdapterResponseError(AdapterError):
    """网络或响应格式错误。"""


class AdapterRateLimitError(AdapterError):
    """服务端限流（HTTP 429）；``retry_after`` 为建议等待秒数。"""

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


# ============================================================
# 传输层
# ============================================================

Transport = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]


def _urllib_transport(
    url: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """默认 HTTP 传输：POST JSON，返回解析后的 JSON。"""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers=dict(headers),
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:  # 4xx / 5xx
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:  # noqa: BLE001 - 读错误体失败不应掩盖原始错误
            detail = ""
        if exc.code == 429:
            retry_after = None
            raw_retry_after = exc.headers.get("Retry-After")
            if raw_retry_after:
                try:
                    retry_after = float(raw_retry_after)
                except ValueError:
                    try:
                        moment = email.utils.parsedate_to_datetime(
                            raw_retry_after
                        )
                        if moment.tzinfo is None:
                            moment = moment.replace(tzinfo=timezone.utc)
                        retry_after = max(
                            0.0,
                            (
                                moment - datetime.now(timezone.utc)
                            ).total_seconds(),
                        )
                    except Exception:  # noqa: BLE001 - 解析失败退化为 None
                        retry_after = None
            raise AdapterRateLimitError(
                f"HTTP 429 from {url}: {detail}",
                retry_after=retry_after,
            ) from exc
        raise AdapterResponseError(
            f"HTTP {exc.code} from {url}: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise AdapterResponseError(
            f"network error calling {url}: {exc.reason}"
        ) from exc
    except TimeoutError as exc:
        raise AdapterResponseError(f"timeout calling {url}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AdapterResponseError(
            f"non-JSON response from {url}: {raw[:200]}"
        ) from exc


# ============================================================
# 适配器规格
# ============================================================


@dataclass(frozen=True)
class AdapterSpec:
    """单个助手的调用规格，全部通过环境变量配置。"""

    agent_id: str
    display_name: str
    api_key_env: str
    base_url_env: str
    model_env: str
    default_base_url: str
    default_model: str
    notes: str = ""

    def resolve(
        self,
        env: Mapping[str, str],
    ) -> tuple[str, str, str]:
        """返回 (api_key, base_url, model)，不做网络请求。"""
        api_key = (env.get(self.api_key_env) or "").strip()
        base_url = (env.get(self.base_url_env) or "").strip()
        model = (env.get(self.model_env) or "").strip()

        if not base_url:
            base_url = self.default_base_url
        if not model:
            model = self.default_model

        return api_key, base_url, model


ADAPTER_SPECS: dict[str, AdapterSpec] = {
    "chatgpt": AdapterSpec(
        agent_id="chatgpt",
        display_name="ChatGPT (CIO)",
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        model_env="OPENAI_MODEL",
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-5.5",
    ),
    "grok": AdapterSpec(
        agent_id="grok",
        display_name="Grok (Market Intelligence)",
        api_key_env="XAI_API_KEY",
        base_url_env="XAI_BASE_URL",
        model_env="XAI_MODEL",
        default_base_url="https://api.x.ai/v1",
        default_model="",  # 模型名以 xAI 控制台为准，不预置猜测值
        notes="xAI 兼容 OpenAI chat/completions 协议；XAI_MODEL 必须显式配置",
    ),
    "hark": AdapterSpec(
        agent_id="hark",
        display_name="Hark (Fundamental Analyst)",
        api_key_env="HARK_API_KEY",
        base_url_env="HARK_BASE_URL",
        model_env="HARK_MODEL",
        default_base_url="",
        default_model="",
        notes=(
            "Hark 未公开文档化的 API；如需接入请自建网关并配置 "
            "HARK_BASE_URL / HARK_API_KEY / HARK_MODEL，否则该席位走人工模式"
        ),
    ),
}


# ============================================================
# 适配器实现
# ============================================================


@dataclass
class GenerationRecord:
    """一次生成的审计信息（不含密钥）。"""

    agent_id: str
    model: str
    base_url: str
    elapsed_seconds: float
    prompt_chars: int
    response_chars: int
    content_sha256: str
    finish_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "model": self.model,
            "base_url": self.base_url,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "prompt_chars": self.prompt_chars,
            "response_chars": self.response_chars,
            "content_sha256": self.content_sha256,
            "finish_reason": self.finish_reason,
        }


@dataclass
class GeneratedReport:
    agent_id: str
    title: str
    content: str
    record: GenerationRecord
    sources: list[dict] | None = None

    @property
    def source(self) -> str:
        return f"api:{self.record.model}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "title": self.title,
            "content": self.content,
            "generation": self.record.to_dict(),
            "sources": self.sources,
        }


class OpenAICompatibleAdapter:
    """OpenAI ``/chat/completions`` 协议的适配器（ChatGPT / Grok / 自建网关）。"""

    def __init__(
        self,
        spec: AdapterSpec,
        api_key: str,
        base_url: str,
        model: str,
        *,
        timeout: float = 120.0,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        transport: Transport | None = None,
    ) -> None:
        if not api_key:
            raise AdapterConfigError(
                f"{spec.agent_id}: missing {spec.api_key_env}"
            )
        if not base_url:
            raise AdapterConfigError(
                f"{spec.agent_id}: missing {spec.base_url_env}"
            )
        if not model:
            raise AdapterConfigError(
                f"{spec.agent_id}: missing {spec.model_env}"
            )

        self.spec = spec
        self.agent_id = spec.agent_id
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._transport = transport or _urllib_transport
        self._api_key = api_key
        self._last_elapsed: float = 0.0
        self._last_finish_reason: str = ""

    # -- 基础信息 --------------------------------------------------

    def is_configured(self) -> bool:
        return True

    def describe(self) -> dict[str, Any]:
        """对外可安全打印的配置摘要（不含密钥）。"""
        return {
            "agent_id": self.agent_id,
            "display_name": self.spec.display_name,
            "base_url": self.base_url,
            "model": self.model,
            "configured": True,
        }

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"

    # -- 调用 ------------------------------------------------------

    def complete(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """调用模型并返回助手正文；失败一律抛 AdapterError 子类。"""
        if not isinstance(prompt, str) or not prompt.strip():
            raise AdapterConfigError("prompt must be a non-empty string")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature
            if temperature is None
            else temperature,
            "max_tokens": self.max_tokens
            if max_tokens is None
            else max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        started = time.perf_counter()
        response = self._transport(
            self.endpoint,
            headers,
            payload,
            self.timeout,
        )
        elapsed = time.perf_counter() - started

        text, finish_reason = self._extract_text(response)
        self._last_elapsed = elapsed
        self._last_finish_reason = finish_reason
        return text

    def _extract_text(
        self,
        response: Mapping[str, Any],
    ) -> tuple[str, str]:
        if not isinstance(response, Mapping):
            raise AdapterResponseError(
                f"{self.agent_id}: response is not a JSON object"
            )

        if response.get("error"):
            message = str(response.get("error"))[:300]
            raise AdapterResponseError(
                f"{self.agent_id}: provider error: {message}"
            )

        choices = response.get("choices")
        if not isinstance(choices, Sequence) or not choices:
            raise AdapterResponseError(
                f"{self.agent_id}: response has no choices"
            )

        first = choices[0]
        if not isinstance(first, Mapping):
            raise AdapterResponseError(
                f"{self.agent_id}: malformed choice entry"
            )

        message = first.get("message") or {}
        content = message.get("content") if isinstance(message, Mapping) else None

        # 部分网关以 list 形式返回分段内容
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, Mapping) and item.get("text"):
                    parts.append(str(item["text"]))
            content = "".join(parts)

        if not isinstance(content, str) or not content.strip():
            raise AdapterResponseError(
                f"{self.agent_id}: empty message content"
            )

        finish_reason = str(first.get("finish_reason") or "")
        return content.strip(), finish_reason


# ============================================================
# 注册表
# ============================================================


@dataclass
class AdapterRegistry:
    """按 agent_id 存放可用适配器，并记录未配置的原因。"""

    adapters: dict[str, OpenAICompatibleAdapter] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)

    def available(self) -> list[str]:
        return sorted(self.adapters)

    def is_available(self, agent_id: str) -> bool:
        return agent_id in self.adapters

    def get(self, agent_id: str) -> OpenAICompatibleAdapter:
        try:
            return self.adapters[agent_id]
        except KeyError as exc:
            reason = self.skipped.get(agent_id, "not registered")
            raise AdapterUnavailableError(
                f"{agent_id} is not callable: {reason}"
            ) from exc

    def describe(self) -> dict[str, Any]:
        return {
            "available": self.available(),
            "skipped": dict(self.skipped),
        }


def describe_seat_status(registry: AdapterRegistry) -> str:
    """启动自检：列出哪些席位可调用、哪些只能人工导入。"""
    registered = registry.adapters
    skipped = registry.skipped
    seats = []
    for seat in ("chatgpt", "grok", "hark"):
        if seat in registered:
            status = "available"
        elif seat in skipped:
            status = f"skipped ({skipped[seat]})"
        else:
            status = "not_registered"
        seats.append(f"{seat}={status}")
    first_line = "Seats: " + ", ".join(seats)
    skipped_seats = [
        seat for seat in ("chatgpt", "grok", "hark") if seat in skipped
    ]
    second_line = (
        "Manual import required for: " + ", ".join(skipped_seats)
        if skipped_seats
        else "All seats callable."
    )
    return f"{first_line}\n{second_line}"


def load_env_file(path: str | Path | None = None) -> dict[str, str]:
    """极简 ``.env`` 解析：只读键值，不写回环境，不打印内容。"""
    env_path = Path(path) if path is not None else Path(".env")
    values: dict[str, str] = {}

    if not env_path.is_file():
        return values

    for raw in env_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        value = value.strip().strip('"').strip("'")
        values[key] = value

    return values


def build_registry(
    env: Mapping[str, str] | None = None,
    *,
    env_file: str | Path | None = None,
    transport: Transport | None = None,
    timeout: float = 120.0,
    only: Sequence[str] | None = None,
) -> AdapterRegistry:
    """按环境变量装配适配器。

    优先级：显式传入的 ``env`` > 进程环境 > ``.env`` 文件。
    缺少任一项配置的助手不会创建适配器，原因写入 ``skipped``。
    """
    file_env = load_env_file(env_file) if env_file is not None else load_env_file()

    merged: dict[str, str] = dict(file_env)
    if env is not None:
        merged.update({k: v for k, v in env.items() if v})
    else:
        merged.update({k: v for k, v in os.environ.items() if v})

    registry = AdapterRegistry()
    targets = list(only) if only else list(ADAPTER_SPECS)

    for agent_id in targets:
        spec = ADAPTER_SPECS.get(agent_id)
        if spec is None:
            registry.skipped[agent_id] = "unknown agent_id"
            continue

        api_key, base_url, model = spec.resolve(merged)
        missing = []
        if not api_key:
            missing.append(spec.api_key_env)
        if not base_url:
            missing.append(spec.base_url_env)
        if not model:
            missing.append(spec.model_env)

        if missing:
            reason = "missing: " + ", ".join(missing)
            if spec.notes:
                reason = f"{reason} ({spec.notes})"
            registry.skipped[agent_id] = reason
            continue

        registry.adapters[agent_id] = OpenAICompatibleAdapter(
            spec=spec,
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            transport=transport,
        )

    return registry


# ============================================================
# 提示词与报告生成
# ============================================================


def build_agent_prompt(
    agent_id: str,
    *,
    task_id: str,
    subject: str,
    ticker: str,
    as_of_date: str,
    investment_horizon: str = "中期（1-6 个月）",
    risk_profile: str = "中性",
    questions: str = "",
    team_reports: str = "",
    library: Any = None,
) -> str:
    """按角色加载提示词，追加统一输出契约。"""
    role = AGENT_ROLE_NAMES.get(agent_id)
    if role is None:
        raise AdapterConfigError(f"unknown agent_id: {agent_id}")

    if library is None:
        from ai_team.prompt_library import PromptLibrary

        library = PromptLibrary()

    variables = {
        "TASK_ID": task_id,
        "TASK_TITLE": f"Multi-AI research on {subject} ({ticker})",
        "SUBJECT": subject,
        "TICKER": ticker,
        "AS_OF_DATE": as_of_date,
        "INVESTMENT_HORIZON": investment_horizon,
        "RISK_PROFILE": risk_profile,
        "TEAM_REPORTS": team_reports or "（本轮为首轮独立研究，暂无其他助手报告）",
        "QUESTIONS": questions
        or (
            "- 收入与利润的同比增长是否可持续？\n"
            "- 毛利率、存货、应收与经营现金流是否互相印证？\n"
            "- 当前估值相对同业处于什么位置？\n"
            "- 哪些证据会推翻你的结论？"
        ),
        # 其余角色提示词里的可选占位符
        "EXISTING_RESEARCH": team_reports or "无",
        "INDUSTRY": "未指定",
        "REGION": "A 股（中国内地）",
    }

    prompt_name = library.ROLE_PROMPTS[role]
    raw_prompt = library.load_prompt(prompt_name)

    # 角色提示词可能新增占位符；未覆盖的一律填「未提供」，
    # 避免因一个可选字段缺失就整份渲染失败。
    for placeholder in library.PLACEHOLDER_PATTERN.findall(raw_prompt):
        variables.setdefault(placeholder, "未提供")

    base_prompt = library.render_prompt(
        prompt_name,
        variables=variables,
        strict=True,
    )
    return base_prompt.rstrip() + REPORT_CONTRACT


def generate_reports(
    registry: AdapterRegistry,
    *,
    task_id: str,
    subject: str,
    ticker: str,
    as_of_date: str,
    questions: str = "",
    team_reports: str = "",
    library: Any = None,
    only: Sequence[str] | None = None,
    rate_limit_retries: int = 2,
    base_retry_wait: float = 5.0,
    max_retry_wait: float = 60.0,
) -> tuple[list[GeneratedReport], dict[str, str]]:
    """逐个助手生成报告。

    返回 ``(reports, failures)``；单个助手失败不影响其他助手。
    未配置的助手直接写入 ``failures``，不发任何请求。
    """
    reports: list[GeneratedReport] = []
    failures: dict[str, str] = {}
    if only:
        targets = list(only)
    else:
        # 未配置的助手也要出现在 failures 里，否则缺口会被静默吞掉
        targets = sorted(set(registry.adapters) | set(registry.skipped))

    for agent_id in targets:
        adapter = registry.adapters.get(agent_id)
        if adapter is None:
            failures[agent_id] = (
                "AdapterUnavailableError: "
                + registry.skipped.get(agent_id, "not registered")
            )
            continue

        prompt = build_agent_prompt(
            agent_id,
            task_id=task_id,
            subject=subject,
            ticker=ticker,
            as_of_date=as_of_date,
            questions=questions,
            team_reports=team_reports,
            library=library,
        )

        retries = 0
        content: str | None = None
        while True:
            try:
                content = adapter.complete(prompt)
                break
            except AdapterRateLimitError as exc:
                if retries >= rate_limit_retries:
                    failures[agent_id] = f"{type(exc).__name__}: {exc}"
                    break
                wait = (
                    exc.retry_after
                    if exc.retry_after is not None
                    else base_retry_wait
                )
                if wait > max_retry_wait:
                    failures[agent_id] = (
                        f"{type(exc).__name__}: rate limit retry_after "
                        f"exceeds cap ({wait})"
                    )
                    break
                time.sleep(wait)
                retries += 1
            except AdapterError as exc:
                failures[agent_id] = f"{type(exc).__name__}: {exc}"
                break

        if content is None:
            continue

        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        sources = extract_sources_from_content(content)
        record = GenerationRecord(
            agent_id=agent_id,
            model=adapter.model,
            base_url=adapter.base_url,
            elapsed_seconds=getattr(adapter, "_last_elapsed", 0.0),
            prompt_chars=len(prompt),
            response_chars=len(content),
            content_sha256=digest,
            finish_reason=getattr(adapter, "_last_finish_reason", ""),
        )
        reports.append(
            GeneratedReport(
                agent_id=agent_id,
                title=f"{agent_id} research report ({adapter.model})",
                content=content,
                record=record,
                sources=sources,
            )
        )

    return reports, failures


def validate_report_sections(content: str) -> list[str]:
    """返回缺失的必填小节（空列表表示齐全）。"""
    lines = [
        _normalize_heading(line)
        for line in content.splitlines()
    ]
    missing = [s for s in REQUIRED_SECTIONS if _normalize_heading(s) not in lines]
    return missing


def _normalize_heading(line: str) -> str:
    text = line.strip()
    while text.startswith("#"):
        text = text[1:]
    return text.strip().rstrip("#").strip().lower()


__all__ = [
    "ADAPTER_SPECS",
    "AGENT_ROLE_NAMES",
    "AdapterConfigError",
    "AdapterError",
    "AdapterRateLimitError",
    "AdapterRegistry",
    "AdapterResponseError",
    "AdapterSpec",
    "AdapterUnavailableError",
    "GeneratedReport",
    "GenerationRecord",
    "OpenAICompatibleAdapter",
    "REQUIRED_SECTIONS",
    "build_agent_prompt",
    "build_registry",
    "generate_reports",
    "load_env_file",
    "validate_report_sections",
]
