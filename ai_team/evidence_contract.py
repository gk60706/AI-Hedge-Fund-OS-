"""Evidence traceability contract for AI team agent reports.

Pure validation helpers, no third-party dependencies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlsplit


ALLOWED_SOURCE_TYPES = frozenset({
    "official",
    "company_filing",
    "government",
    "exchange",
    "academic",
    "financial_data",
    "news_media",
    "industry_research",
    "other",
})

ALLOWED_VERIFICATION_STATUSES = frozenset({
    "verified",
    "unverified",
})


def validate_evidence_contract(
    sources: Any,
) -> dict[str, Any]:
    """
    Validate structured evidence sources of an agent report.

    Requirements:
    1. at least one source;
    2. every source has a non-empty name;
    3. every source has an original HTTP/HTTPS link;
    4. every source has an ISO 8601 publication timestamp with timezone;
    5. every source has a non-empty data_period;
    6. every source is explicitly marked verified or unverified.

    unverified is a legal state and is not rejected by itself,
    but verification_status may not be omitted.

    Returns:
        {
            "valid": bool,
            "source_count": int,
            "verified_count": int,
            "unverified_count": int,
            "errors": [
                {
                    "source_index": int | None,
                    "field": str,
                    "code": str,
                    "message": str,
                }
            ],
            "unverified_sources": [int, ...],
        }
    """
    errors: list[dict[str, Any]] = []
    unverified_sources: list[int] = []
    verified_count = 0
    unverified_count = 0

    def add_error(
        source_index: int | None,
        field: str,
        code: str,
        message: str,
    ) -> None:
        errors.append({
            "source_index": source_index,
            "field": field,
            "code": code,
            "message": message,
        })

    if not isinstance(sources, list) or not sources:
        add_error(
            None,
            "sources",
            "missing_sources",
            "至少需要提供一个结构化证据来源。",
        )
        return {
            "valid": False,
            "source_count": 0,
            "verified_count": 0,
            "unverified_count": 0,
            "errors": errors,
            "unverified_sources": [],
        }

    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            add_error(
                index,
                "source",
                "invalid_source",
                "来源必须是对象。",
            )
            continue

        # 1. Source name.
        name = source.get("name")
        if not isinstance(name, str) or not name.strip():
            add_error(
                index,
                "name",
                "missing_name",
                "来源名称不能为空。",
            )

        # 2. Original link: must be an HTTP/HTTPS URL.
        url = source.get("url")
        if not isinstance(url, str) or not url.strip():
            add_error(
                index,
                "url",
                "missing_url",
                "必须提供原始来源链接。",
            )
        else:
            try:
                parsed_url = urlsplit(url.strip())
                valid_url = (
                    parsed_url.scheme.lower() in {"http", "https"}
                    and bool(parsed_url.hostname)
                    and bool(parsed_url.netloc)
                    and not any(char.isspace() for char in url.strip())
                )
            except (TypeError, ValueError):
                valid_url = False

            if not valid_url:
                add_error(
                    index,
                    "url",
                    "invalid_url",
                    "来源链接必须是有效的 HTTP/HTTPS 原始链接。",
                )

        # 3. Publication date: ISO 8601 timestamp with timezone.
        published_at = source.get("published_at")
        if not isinstance(published_at, str) or not published_at.strip():
            add_error(
                index,
                "published_at",
                "missing_published_at",
                "必须提供来源发布日期。",
            )
        else:
            try:
                normalized = published_at.strip()
                if "T" not in normalized:
                    raise ValueError("missing time component")

                if normalized.endswith("Z"):
                    normalized = normalized[:-1] + "+00:00"

                parsed_datetime = datetime.fromisoformat(normalized)

                if (
                    parsed_datetime.tzinfo is None
                    or parsed_datetime.utcoffset() is None
                ):
                    raise ValueError("timezone is required")

            except (TypeError, ValueError, OverflowError):
                add_error(
                    index,
                    "published_at",
                    "invalid_published_at",
                    "发布日期必须是带时区的 ISO 8601 时间戳。",
                )

        # 4. Data period.
        data_period = source.get("data_period")
        if not isinstance(data_period, str) or not data_period.strip():
            add_error(
                index,
                "data_period",
                "missing_data_period",
                "必须明确标注来源数据期间。",
            )

        # 5. Source type.
        source_type = source.get("source_type")
        if (
            not isinstance(source_type, str)
            or source_type not in ALLOWED_SOURCE_TYPES
        ):
            add_error(
                index,
                "source_type",
                "invalid_source_type",
                "必须提供有效的来源类型。",
            )

        # 6. Verification status: no omission, no unknown value.
        verification_status = source.get("verification_status")

        if (
            not isinstance(verification_status, str)
            or verification_status not in ALLOWED_VERIFICATION_STATUSES
        ):
            add_error(
                index,
                "verification_status",
                "missing_or_invalid_verification_status",
                "必须明确标记 verified 或 unverified。",
            )
        elif verification_status == "verified":
            verified_count += 1
        else:
            unverified_count += 1
            unverified_sources.append(index)

    return {
        "valid": not errors,
        "source_count": len(sources),
        "verified_count": verified_count,
        "unverified_count": unverified_count,
        "errors": errors,
        "unverified_sources": unverified_sources,
    }
