"""Unit tests for the evidence traceability contract."""

from ai_team.evidence_contract import validate_evidence_contract


def _valid_source():
    return {
        "name": "Example Company 2026 Q2 Report",
        "url": "https://example.com/reports/2026-q2",
        "published_at": "2026-08-15T10:00:00+08:00",
        "description": "Company quarterly report",
        "data_period": "2026-Q2",
        "source_type": "company_filing",
        "verification_status": "verified",
        "verification_note": "Published on the company's official website.",
    }


def test_complete_verified_source_passes_with_counts():
    result = validate_evidence_contract([
        _valid_source(),
    ])

    assert result["valid"] is True
    assert result["source_count"] == 1
    assert result["verified_count"] == 1
    assert result["unverified_count"] == 0
    assert result["errors"] == []
    assert result["unverified_sources"] == []


def test_missing_url_is_rejected():
    source = _valid_source()
    source.pop("url")

    result = validate_evidence_contract([source])

    assert result["valid"] is False
    assert result["errors"][0]["code"] == "missing_url"


def test_missing_data_period_is_rejected():
    source = _valid_source()
    source.pop("data_period")

    result = validate_evidence_contract([source])

    assert result["valid"] is False
    assert result["errors"][0]["code"] == "missing_data_period"


def test_unverified_source_is_allowed_when_marked():
    source = _valid_source()
    source["verification_status"] = "unverified"

    result = validate_evidence_contract([source])

    assert result["valid"] is True
    assert result["unverified_count"] == 1
    assert result["unverified_sources"] == [0]


def test_missing_verification_status_is_rejected():
    source = _valid_source()
    source.pop("verification_status")

    result = validate_evidence_contract([source])

    assert result["valid"] is False
    assert (
        result["errors"][0]["code"]
        == "missing_or_invalid_verification_status"
    )


def test_empty_sources_is_rejected():
    result = validate_evidence_contract([])

    assert result["valid"] is False
    assert result["source_count"] == 0
    assert result["errors"][0]["code"] == "missing_sources"
