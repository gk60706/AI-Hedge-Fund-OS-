
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_team.schema_validator import (
    SchemaDefinitionError,
    SchemaNotFoundError,
    SchemaValidationError,
    SchemaValidator,
)


@pytest.fixture
def schema_dir(tmp_path: Path) -> Path:
    """Create an isolated schema directory."""

    directory = tmp_path / "schemas"
    directory.mkdir()
    return directory


@pytest.fixture
def validator() -> SchemaValidator:
    """Use the project's default schema directory."""

    return SchemaValidator()


@pytest.fixture
def custom_validator(schema_dir: Path) -> SchemaValidator:
    """Use an isolated schema directory."""

    return SchemaValidator(schema_dir=schema_dir)


@pytest.fixture
def valid_task() -> dict:
    return {
        "task_id": "task-001",
        "task_type": "research",
        "title": "Research company fundamentals",
        "description": "Analyze company business and financial data.",
        "status": "pending",
        "priority": 5,
        "assigned_role": "ANALYST",
        "assigned_agent": "hark-analyst",
        "symbol": "300394",
        "market": "CN",
        "input_data": {
            "source": "local_test_data"
        },
        "context": {},
        "dependencies": [],
        "created_at": "2026-01-01T09:00:00Z",
        "started_at": None,
        "completed_at": None,
        "deadline": None,
        "error_message": None,
        "metadata": {},
    }


@pytest.fixture
def valid_report() -> dict:
    return {
        "report_id": "report-001",
        "task_id": "task-001",
        "agent_role": "ANALYST",
        "agent_name": "hark-analyst",
        "status": "completed",
        "symbol": "300394",
        "market": "CN",
        "summary": "The company has a growing optical communication business.",
        "conclusion": "Further research is required.",
        "findings": [
            {
                "title": "Business growth",
                "content": "Revenue growth should be evaluated against industry demand.",
                "importance": "high",
                "evidence": [
                    "Test evidence only."
                ],
            }
        ],
        "risks": [
            "Valuation risk."
        ],
        "recommendations": [
            "Monitor quarterly results."
        ],
        "confidence": 0.82,
        "sources": [
            {
                "name": "Local test source",
                "url": "https://example.com/report",
                "published_at": "2026-01-01T08:00:00Z",
                "description": "Test source."
            }
        ],
        "created_at": "2026-01-01T09:30:00Z",
        "metadata": {},
    }


@pytest.fixture
def valid_debate() -> dict:
    return {
        "debate_id": "debate-001",
        "task_id": "task-001",
        "topic": "Evaluate the investment outlook.",
        "symbol": "300394",
        "status": "completed",
        "max_rounds": 3,
        "rounds": [
            {
                "round_number": 1,
                "arguments": [
                    {
                        "agent_role": "ANALYST",
                        "position": "support",
                        "argument": "Industry demand may support future growth.",
                        "evidence": [
                            "Illustrative evidence."
                        ],
                        "confidence": 0.75,
                        "response_to": None,
                    },
                    {
                        "agent_role": "RISK_MANAGER",
                        "position": "oppose",
                        "argument": "Valuation and execution risks remain.",
                        "evidence": [],
                        "confidence": 0.8,
                        "response_to": "ANALYST",
                    }
                ],
                "round_summary": "The agents identified both growth drivers and risks."
            }
        ],
        "final_position": "neutral",
        "final_summary": "More evidence is required.",
        "created_at": "2026-01-01T10:00:00Z",
        "completed_at": "2026-01-01T10:10:00Z",
        "metadata": {},
    }


@pytest.fixture
def valid_consensus() -> dict:
    return {
        "consensus_id": "consensus-001",
        "task_id": "task-001",
        "debate_id": "debate-001",
        "status": "partial",
        "conclusion": "The team reached partial agreement.",
        "agreement_ratio": 0.75,
        "participating_agents": [
            "chatgpt-cio",
            "grok-intelligence",
            "hark-analyst",
        ],
        "supporting_arguments": [
            "Potential industry growth."
        ],
        "opposing_arguments": [
            "Valuation uncertainty."
        ],
        "unresolved_questions": [
            "Future order growth."
        ],
        "confidence": 0.72,
        "created_at": "2026-01-01T10:20:00Z",
        "metadata": {},
    }


@pytest.fixture
def valid_decision() -> dict:
    return {
        "decision_id": "decision-001",
        "task_id": "task-001",
        "consensus_id": "consensus-001",
        "symbol": "300394",
        "market": "CN",
        "company_name": "Test Company",
        "decision": "watch",
        "rationale": "The research evidence is not yet sufficient for a stronger conclusion.",
        "risk_level": "moderate",
        "confidence": 0.68,
        "target_price": 120.0,
        "entry_price_low": 100.0,
        "entry_price_high": 105.0,
        "stop_loss_price": 95.0,
        "position_suggestion": 0.05,
        "investment_horizon": "short_term",
        "key_catalysts": [
            "Potential demand recovery."
        ],
        "key_risks": [
            "Valuation volatility."
        ],
        "invalidation_conditions": [
            "Fundamental assumptions are invalidated."
        ],
        "paper_trade_only": True,
        "created_at": "2026-01-01T11:00:00Z",
        "valid_until": "2026-01-10T15:00:00Z",
        "metadata": {},
    }


# =========================================================
# Default schema directory and schema loading
# =========================================================


EXPECTED_SCHEMAS = {
    "agent_task",
    "agent_report",
    "debate_record",
    "consensus_result",
    "investment_decision",
}


def test_default_schema_directory_exists(validator: SchemaValidator):
    assert validator.schema_dir.exists()
    assert validator.schema_dir.is_dir()


def test_default_schema_directory_contains_all_schemas(
    validator: SchemaValidator,
):
    assert EXPECTED_SCHEMAS.issubset(set(validator.list_schemas()))


def test_list_schemas_is_sorted(validator: SchemaValidator):
    schemas = validator.list_schemas()
    assert schemas == sorted(schemas)


@pytest.mark.parametrize(
    "schema_name",
    sorted(EXPECTED_SCHEMAS),
)
def test_load_each_schema(
    validator: SchemaValidator,
    schema_name: str,
):
    schema = validator.load_schema(schema_name)

    assert isinstance(schema, dict)
    assert schema["$schema"] == (
        "https://json-schema.org/draft/2020-12/schema"
    )
    assert schema["type"] == "object"


def test_load_schema_accepts_suffix(validator: SchemaValidator):
    schema = validator.load_schema("agent_task.schema.json")
    assert schema["title"] == "AI Team Agent Task"


def test_load_schema_returns_independent_copy(
    validator: SchemaValidator,
):
    first = validator.load_schema("agent_task")
    first["title"] = "Changed title"

    second = validator.load_schema("agent_task")

    assert second["title"] == "AI Team Agent Task"


def test_clear_cache(validator: SchemaValidator):
    validator.load_schema("agent_task")

    assert "agent_task" in validator._schema_cache

    validator.clear_cache()

    assert validator._schema_cache == {}


# =========================================================
# Schema name validation
# =========================================================


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("agent_task", "agent_task"),
        ("agent_task.schema.json", "agent_task"),
        ("agent_task.json", "agent_task"),
        ("  agent_report  ", "agent_report"),
        ("investment_decision", "investment_decision"),
    ],
)
def test_normalize_schema_name(
    validator: SchemaValidator,
    raw: str,
    expected: str,
):
    assert validator.normalize_schema_name(raw) == expected


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",
        " ",
        "../agent_task",
        "../../secret",
        "schemas/agent_task",
        r"..\agent_task",
        "agent_task/../../secret",
        ".",
        "..",
        "agent task",
        "agent.task",
    ],
)
def test_normalize_schema_name_rejects_invalid_values(
    validator: SchemaValidator,
    invalid_name: str,
):
    with pytest.raises((ValueError, TypeError)):
        validator.normalize_schema_name(invalid_name)


def test_normalize_schema_name_rejects_non_string(
    validator: SchemaValidator,
):
    with pytest.raises(TypeError):
        validator.normalize_schema_name(123)


def test_load_unknown_schema_raises(
    validator: SchemaValidator,
):
    with pytest.raises(SchemaNotFoundError):
        validator.load_schema("unknown_schema")


def test_schema_path_rejects_path_traversal(
    validator: SchemaValidator,
):
    with pytest.raises(ValueError):
        validator._schema_path("../outside")


# =========================================================
# JSON file and schema definition validation
# =========================================================


def test_invalid_json_schema_file_raises(
    schema_dir: Path,
):
    path = schema_dir / "broken.schema.json"
    path.write_text("{invalid json", encoding="utf-8")

    validator = SchemaValidator(schema_dir=schema_dir)

    with pytest.raises(SchemaDefinitionError):
        validator.load_schema("broken")


def test_schema_file_must_contain_object(
    schema_dir: Path,
):
    path = schema_dir / "not_object.schema.json"
    path.write_text('["not", "object"]', encoding="utf-8")

    validator = SchemaValidator(schema_dir=schema_dir)

    with pytest.raises(SchemaDefinitionError):
        validator.load_schema("not_object")


def test_schema_rejects_unknown_keyword(
    validator: SchemaValidator,
):
    schema = {
        "type": "string",
        "unknownKeyword": True,
    }

    with pytest.raises(SchemaDefinitionError):
        validator.validate_schema(schema)


def test_schema_rejects_unsupported_type(
    validator: SchemaValidator,
):
    schema = {
        "type": "unsupported_type",
    }

    with pytest.raises(SchemaDefinitionError):
        validator.validate_schema(schema)


def test_schema_rejects_invalid_pattern(
    validator: SchemaValidator,
):
    schema = {
        "type": "string",
        "pattern": "[",
    }

    with pytest.raises(SchemaDefinitionError):
        validator.validate_schema(schema)


def test_schema_rejects_external_ref(
    validator: SchemaValidator,
):
    schema = {
        "$ref": "https://example.com/schema.json",
    }

    with pytest.raises(SchemaDefinitionError):
        validator.validate_schema(schema)


def test_schema_rejects_invalid_format(
    validator: SchemaValidator,
):
    schema = {
        "type": "string",
        "format": "unknown-format",
    }

    with pytest.raises(SchemaDefinitionError):
        validator.validate_schema(schema)


# =========================================================
# Valid business object validation
# =========================================================


def test_valid_agent_task(
    validator: SchemaValidator,
    valid_task: dict,
):
    result = validator.validate(valid_task, "agent_task")

    assert result.valid is True
    assert result.issues == ()


def test_valid_agent_report(
    validator: SchemaValidator,
    valid_report: dict,
):
    result = validator.validate(valid_report, "agent_report")

    assert result.valid is True
    assert result.issues == ()


def test_valid_debate_record(
    validator: SchemaValidator,
    valid_debate: dict,
):
    result = validator.validate(valid_debate, "debate_record")

    assert result.valid is True
    assert result.issues == ()


def test_valid_consensus_result(
    validator: SchemaValidator,
    valid_consensus: dict,
):
    result = validator.validate(
        valid_consensus,
        "consensus_result",
    )

    assert result.valid is True
    assert result.issues == ()


def test_valid_investment_decision(
    validator: SchemaValidator,
    valid_decision: dict,
):
    result = validator.validate(
        valid_decision,
        "investment_decision",
    )

    assert result.valid is True
    assert result.issues == ()
# =========================================================
# Required properties and additional properties
# =========================================================


def test_task_missing_required_field(
    validator: SchemaValidator,
    valid_task: dict,
):
    del valid_task["task_id"]

    result = validator.validate(valid_task, "agent_task")

    assert result.valid is False
    assert any(
        issue.keyword == "required"
        for issue in result.issues
    )


def test_task_rejects_additional_property(
    validator: SchemaValidator,
    valid_task: dict,
):
    valid_task["unexpected_field"] = "not allowed"

    result = validator.validate(valid_task, "agent_task")

    assert result.valid is False
    assert any(
        issue.keyword == "additionalProperties"
        for issue in result.issues
    )


def test_report_rejects_invalid_nested_finding(
    validator: SchemaValidator,
    valid_report: dict,
):
    valid_report["findings"][0]["unexpected"] = "bad"

    result = validator.validate(valid_report, "agent_report")

    assert result.valid is False
    assert any(
        issue.keyword == "additionalProperties"
        for issue in result.issues
    )


def test_report_rejects_missing_finding_title(
    validator: SchemaValidator,
    valid_report: dict,
):
    del valid_report["findings"][0]["title"]

    result = validator.validate(valid_report, "agent_report")

    assert result.valid is False
    assert any(
        issue.keyword == "required"
        for issue in result.issues
    )


# =========================================================
# Type, enum and numeric constraints
# =========================================================


def test_task_rejects_invalid_status(
    validator: SchemaValidator,
    valid_task: dict,
):
    valid_task["status"] = "unknown"

    result = validator.validate(valid_task, "agent_task")

    assert result.valid is False
    assert any(
        issue.keyword == "enum"
        for issue in result.issues
    )


def test_task_rejects_invalid_priority(
    validator: SchemaValidator,
    valid_task: dict,
):
    valid_task["priority"] = 100

    result = validator.validate(valid_task, "agent_task")

    assert result.valid is False
    assert any(
        issue.keyword == "maximum"
        for issue in result.issues
    )


def test_task_rejects_boolean_priority(
    validator: SchemaValidator,
    valid_task: dict,
):
    valid_task["priority"] = True

    result = validator.validate(valid_task, "agent_task")

    assert result.valid is False
    assert any(
        issue.keyword == "type"
        for issue in result.issues
    )


def test_report_rejects_confidence_above_one(
    validator: SchemaValidator,
    valid_report: dict,
):
    valid_report["confidence"] = 1.5

    result = validator.validate(valid_report, "agent_report")

    assert result.valid is False
    assert any(
        issue.keyword == "maximum"
        for issue in result.issues
    )


def test_consensus_rejects_negative_agreement_ratio(
    validator: SchemaValidator,
    valid_consensus: dict,
):
    valid_consensus["agreement_ratio"] = -0.1

    result = validator.validate(
        valid_consensus,
        "consensus_result",
    )

    assert result.valid is False
    assert any(
        issue.keyword == "minimum"
        for issue in result.issues
    )


def test_decision_rejects_invalid_decision(
    validator: SchemaValidator,
    valid_decision: dict,
):
    valid_decision["decision"] = "execute_order"

    result = validator.validate(
        valid_decision,
        "investment_decision",
    )

    assert result.valid is False
    assert any(
        issue.keyword == "enum"
        for issue in result.issues
    )


def test_decision_rejects_zero_target_price(
    validator: SchemaValidator,
    valid_decision: dict,
):
    valid_decision["target_price"] = 0

    result = validator.validate(
        valid_decision,
        "investment_decision",
    )

    assert result.valid is False
    assert any(
        issue.keyword == "exclusiveMinimum"
        for issue in result.issues
    )


def test_decision_rejects_position_above_one(
    validator: SchemaValidator,
    valid_decision: dict,
):
    valid_decision["position_suggestion"] = 1.5

    result = validator.validate(
        valid_decision,
        "investment_decision",
    )

    assert result.valid is False
    assert any(
        issue.keyword == "maximum"
        for issue in result.issues
    )


# =========================================================
# String patterns and formats
# =========================================================


def test_task_rejects_invalid_stock_symbol(
    validator: SchemaValidator,
    valid_task: dict,
):
    valid_task["symbol"] = "30039A"

    result = validator.validate(valid_task, "agent_task")

    assert result.valid is False
    assert any(
        issue.keyword == "pattern"
        for issue in result.issues
    )


def test_task_rejects_invalid_datetime(
    validator: SchemaValidator,
    valid_task: dict,
):
    valid_task["created_at"] = "not-a-date"

    result = validator.validate(valid_task, "agent_task")

    assert result.valid is False
    assert any(
        issue.keyword == "format"
        for issue in result.issues
    )


def test_report_rejects_invalid_source_url(
    validator: SchemaValidator,
    valid_report: dict,
):
    valid_report["sources"][0]["url"] = "not-a-uri"

    result = validator.validate(valid_report, "agent_report")

    assert result.valid is False
    assert any(
        issue.keyword == "format"
        for issue in result.issues
    )


# =========================================================
# Array validation
# =========================================================


def test_task_rejects_duplicate_dependencies(
    validator: SchemaValidator,
    valid_task: dict,
):
    valid_task["dependencies"] = [
        "task-002",
        "task-002",
    ]

    result = validator.validate(valid_task, "agent_task")

    assert result.valid is False
    assert any(
        issue.keyword == "uniqueItems"
        for issue in result.issues
    )


def test_consensus_rejects_duplicate_agents(
    validator: SchemaValidator,
    valid_consensus: dict,
):
    valid_consensus["participating_agents"] = [
        "agent-a",
        "agent-a",
    ]

    result = validator.validate(
        valid_consensus,
        "consensus_result",
    )

    assert result.valid is False
    assert any(
        issue.keyword == "uniqueItems"
        for issue in result.issues
    )


def test_debate_rejects_empty_rounds(
    validator: SchemaValidator,
    valid_debate: dict,
):
    valid_debate["rounds"] = []

    result = validator.validate(valid_debate, "debate_record")

    assert result.valid is False
    assert any(
        issue.keyword == "minItems"
        for issue in result.issues
    )


# =========================================================
# validate_or_raise
# =========================================================


def test_validate_or_raise_returns_result_for_valid_data(
    validator: SchemaValidator,
    valid_task: dict,
):
    result = validator.validate_or_raise(
        valid_task,
        "agent_task",
    )

    assert result.valid is True


def test_validate_or_raise_raises_for_invalid_data(
    validator: SchemaValidator,
    valid_task: dict,
):
    valid_task["status"] = "invalid"

    with pytest.raises(SchemaValidationError) as exc_info:
        validator.validate_or_raise(
            valid_task,
            "agent_task",
        )

    error = exc_info.value

    assert error.schema_name == "agent_task"
    assert len(error.issues) >= 1
    assert "Validation failed" in str(error)


def test_validation_issue_to_dict(
    validator: SchemaValidator,
    valid_task: dict,
):
    valid_task["priority"] = 100

    result = validator.validate(valid_task, "agent_task")

    issue = result.issues[0]
    data = issue.to_dict()

    assert "path" in data
    assert "message" in data
    assert "keyword" in data


def test_validation_result_to_dict(
    validator: SchemaValidator,
    valid_task: dict,
):
    result = validator.validate(valid_task, "agent_task")
    data = result.to_dict()

    assert data["valid"] is True
    assert data["schema_name"] == "agent_task"
    assert data["issues"] == []


# =========================================================
# Custom schema: $ref
# =========================================================


def test_local_ref_validation(
    schema_dir: Path,
):
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["name"],
        "properties": {
            "name": {
                "$ref": "#/definitions/non_empty_string"
            }
        },
        "definitions": {
            "non_empty_string": {
                "type": "string",
                "minLength": 1
            }
        }
    }

    # This validator intentionally supports a limited keyword set.
    # Use a supported local-reference location through properties instead.
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "name": {
                "$ref": "#/properties/shared_name"
            },
            "shared_name": {
                "type": "string",
                "minLength": 1
            }
        },
        "required": ["name"],
    }

    path = schema_dir / "ref_test.schema.json"
    path.write_text(
        json.dumps(schema),
        encoding="utf-8",
    )

    validator = SchemaValidator(schema_dir=schema_dir)

    valid = validator.validate(
        {"name": "Alice", "shared_name": "Alice"},
        "ref_test",
    )
    invalid = validator.validate(
        {"name": ""},
        "ref_test",
    )

    assert valid.valid is True
    assert invalid.valid is False


def test_unresolvable_local_ref_raises(
    schema_dir: Path,
):
    schema = {
        "type": "object",
        "properties": {
            "name": {
                "$ref": "#/missing/property"
            }
        }
    }

    path = schema_dir / "bad_ref.schema.json"
    path.write_text(
        json.dumps(schema),
        encoding="utf-8",
    )

    validator = SchemaValidator(schema_dir=schema_dir)

    with pytest.raises(SchemaDefinitionError):
        validator.validate(
            {"name": "Alice"},
            "bad_ref",
        )


# =========================================================
# Custom schema: composition keywords
# =========================================================


def test_any_of_validation(
    schema_dir: Path,
):
    schema = {
        "anyOf": [
            {"type": "string"},
            {"type": "integer"},
        ]
    }

    path = schema_dir / "any_of.schema.json"
    path.write_text(json.dumps(schema), encoding="utf-8")

    validator = SchemaValidator(schema_dir=schema_dir)

    assert validator.validate("hello", "any_of").valid
    assert validator.validate(10, "any_of").valid
    assert not validator.validate([], "any_of").valid


def test_all_of_validation(
    schema_dir: Path,
):
    schema = {
        "allOf": [
            {"type": "integer"},
            {"minimum": 1},
            {"maximum": 10},
        ]
    }

    path = schema_dir / "all_of.schema.json"
    path.write_text(json.dumps(schema), encoding="utf-8")

    validator = SchemaValidator(schema_dir=schema_dir)

    assert validator.validate(5, "all_of").valid
    assert not validator.validate(0, "all_of").valid
    assert not validator.validate(11, "all_of").valid


def test_one_of_validation(
    schema_dir: Path,
):
    schema = {
        "oneOf": [
            {"type": "integer"},
            {"type": "string"},
        ]
    }

    path = schema_dir / "one_of.schema.json"
    path.write_text(json.dumps(schema), encoding="utf-8")

    validator = SchemaValidator(schema_dir=schema_dir)

    assert validator.validate(5, "one_of").valid
    assert validator.validate("hello", "one_of").valid
    assert not validator.validate([], "one_of").valid


def test_not_validation(
    schema_dir: Path,
):
    schema = {
        "not": {
            "type": "null"
        }
    }

    path = schema_dir / "not_schema.schema.json"
    path.write_text(json.dumps(schema), encoding="utf-8")

    validator = SchemaValidator(schema_dir=schema_dir)

    assert validator.validate("value", "not_schema").valid
    assert not validator.validate(None, "not_schema").valid


# =========================================================
# Error limit and constructor validation
# =========================================================


def test_max_errors_must_be_positive():
    with pytest.raises(ValueError):
        SchemaValidator(max_errors=0)


def test_max_errors_limits_reported_issues(
    schema_dir: Path,
):
    schema = {
        "type": "object",
        "required": [
            "a",
            "b",
            "c",
        ],
    }

    path = schema_dir / "many_errors.schema.json"
    path.write_text(json.dumps(schema), encoding="utf-8")

    validator = SchemaValidator(
        schema_dir=schema_dir,
        max_errors=2,
    )

    result = validator.validate({}, "many_errors")

    assert result.valid is False
    assert len(result.issues) == 2


# =========================================================
# Standard-library and safety boundaries
# =========================================================


def test_validator_does_not_expose_trading_methods(
    validator: SchemaValidator,
):
    forbidden_names = {
        "place_order",
        "submit_order",
        "execute_trade",
        "connect_broker",
        "live_trade",
    }

    public_names = {
        name
        for name in dir(validator)
        if not name.startswith("_")
    }

    assert forbidden_names.isdisjoint(public_names)


def test_validator_has_no_api_key_attribute(
    validator: SchemaValidator,
):
    assert not hasattr(validator, "api_key")
    assert not hasattr(validator, "openai_api_key")


if __name__ == "__main__":
    raise SystemExit(
        pytest.main([__file__, "-v"])
    )