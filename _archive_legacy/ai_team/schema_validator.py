"""Standard-library JSON Schema loader and validator for AI Team.

Supported validation keywords:
    $schema, $id, $ref, type, required, properties,
    additionalProperties, items, enum, const,
    minimum, maximum, exclusiveMinimum, exclusiveMaximum,
    minLength, maxLength, pattern,
    minItems, maxItems, uniqueItems,
    minProperties, maxProperties,
    anyOf, allOf, oneOf, not,
    format: date, date-time, time, email, uri.

This module intentionally has no network access and does not provide
broker, order-routing, or live-trading functionality.
"""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse


__all__ = [
    "SchemaValidator",
    "SchemaValidationError",
    "SchemaNotFoundError",
    "SchemaDefinitionError",
    "ValidationIssue",
]


class SchemaValidatorError(Exception):
    """Base exception for schema validation errors."""


class SchemaNotFoundError(SchemaValidatorError):
    """Raised when a requested schema cannot be found."""


class SchemaDefinitionError(SchemaValidatorError):
    """Raised when a schema definition is malformed or unsupported."""


class SchemaValidationError(SchemaValidatorError):
    """Raised when an instance does not satisfy its schema."""

    def __init__(
        self,
        schema_name: str,
        issues: list["ValidationIssue"],
    ) -> None:
        self.schema_name = schema_name
        self.issues = tuple(issues)

        details = "\n".join(
            f"- {issue.path}: {issue.message}"
            for issue in self.issues
        )

        super().__init__(
            f"Validation failed for schema "
            f"'{schema_name}' with {len(self.issues)} issue(s):\n{details}"
        )


@dataclass(frozen=True)
class ValidationIssue:
    """One validation failure."""

    path: str
    message: str
    keyword: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "message": self.message,
            "keyword": self.keyword,
        }


@dataclass(frozen=True)
class ValidationResult:
    """Validation result returned by validate()."""

    valid: bool
    schema_name: str
    issues: tuple[ValidationIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "schema_name": self.schema_name,
            "issues": [
                issue.to_dict()
                for issue in self.issues
            ],
        }


class SchemaValidator:
    """Load and validate local JSON Schema files.

    Args:
        schema_dir:
            Directory containing *.schema.json files.
            Defaults to ai_team/schemas/.
        max_errors:
            Maximum number of validation issues collected per call.
        encoding:
            Schema file encoding.

    Example:
        validator = SchemaValidator()

        result = validator.validate(
            {
                "task_id": "task-001",
                "task_type": "research",
                "title": "Research company",
                "description": "Analyze company fundamentals.",
                "status": "pending",
                "created_at": "2026-01-01T09:00:00Z",
            },
            "agent_task",
        )

        if not result.valid:
            print(result.to_dict())
    """

    SUPPORTED_TYPES = {
        "object",
        "array",
        "string",
        "integer",
        "number",
        "boolean",
        "null",
    }

    SUPPORTED_KEYWORDS = {
        "$schema",
        "$id",
        "$ref",
        "title",
        "description",
        "default",
        "type",
        "required",
        "properties",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minProperties",
        "maxProperties",
        "anyOf",
        "allOf",
        "oneOf",
        "not",
        "format",
    }

    SUPPORTED_FORMATS = {
        "date",
        "date-time",
        "time",
        "email",
        "uri",
    }

    def __init__(
        self,
        schema_dir: str | Path | None = None,
        max_errors: int = 100,
        encoding: str = "utf-8",
    ) -> None:
        if max_errors < 1:
            raise ValueError("max_errors must be greater than zero")

        if schema_dir is None:
            schema_dir = Path(__file__).resolve().parent / "schemas"

        self.schema_dir = Path(schema_dir).expanduser().resolve()
        self.max_errors = max_errors
        self.encoding = encoding
        self._schema_cache: dict[str, dict[str, Any]] = {}

    # ---------------------------------------------------------
    # Schema name and file handling
    # ---------------------------------------------------------

    @staticmethod
    def normalize_schema_name(name: str) -> str:
        """Normalize a schema name and reject path traversal."""

        if not isinstance(name, str):
            raise TypeError("schema name must be a string")

        value = name.strip()

        if not value:
            raise ValueError("schema name cannot be empty")

        if "/" in value or "\\" in value:
            raise ValueError("schema name cannot contain path separators")

        if value in {".", ".."}:
            raise ValueError("invalid schema name")

        if value.endswith(".schema.json"):
            value = value[:-len(".schema.json")]
        elif value.endswith(".json"):
            value = value[:-len(".json")]

        if not value:
            raise ValueError("schema name cannot be empty")

        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("schema name contains invalid characters")

        return value

    def _schema_path(self, name: str) -> Path:
        normalized = self.normalize_schema_name(name)

        path = (
            self.schema_dir /
            f"{normalized}.schema.json"
        ).resolve()

        try:
            path.relative_to(self.schema_dir)
        except ValueError as exc:
            raise ValueError("schema path escapes schema directory") from exc

        return path

    def list_schemas(self) -> list[str]:
        """Return sorted schema names available in the schema directory."""

        if not self.schema_dir.exists():
            return []

        if not self.schema_dir.is_dir():
            raise SchemaDefinitionError(
                f"Schema path is not a directory: {self.schema_dir}"
            )

        return sorted(
            path.name[:-len(".schema.json")]
            for path in self.schema_dir.glob("*.schema.json")
            if path.is_file()
        )

    def load_schema(
        self,
        name: str,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Load a JSON Schema document from the local schema directory."""

        normalized = self.normalize_schema_name(name)

        if use_cache and normalized in self._schema_cache:
            return copy.deepcopy(self._schema_cache[normalized])

        path = self._schema_path(normalized)

        if not path.exists() or not path.is_file():
            raise SchemaNotFoundError(
                f"Schema '{normalized}' not found at {path}"
            )

        try:
            with path.open("r", encoding=self.encoding) as file:
                schema = json.load(file)
        except json.JSONDecodeError as exc:
            raise SchemaDefinitionError(
                f"Invalid JSON in schema '{normalized}': {exc}"
            ) from exc
        except OSError as exc:
            raise SchemaDefinitionError(
                f"Unable to read schema '{normalized}': {exc}"
            ) from exc

        if not isinstance(schema, dict):
            raise SchemaDefinitionError(
                f"Schema '{normalized}' must contain a JSON object"
            )

        self.validate_schema(schema)

        if use_cache:
            self._schema_cache[normalized] = copy.deepcopy(schema)

        return copy.deepcopy(schema)

    def clear_cache(self) -> None:
        """Clear all cached schema documents."""

        self._schema_cache.clear()

    # ---------------------------------------------------------
    # Schema definition validation
    # ---------------------------------------------------------

    def validate_schema(self, schema: Mapping[str, Any]) -> bool:
        """Validate the structure and supported keywords of a schema."""

        if not isinstance(schema, Mapping):
            raise SchemaDefinitionError("schema must be a mapping")

        self._check_schema_node(schema, "$")
        return True

    def _check_schema_node(
        self,
        schema: Mapping[str, Any],
        path: str,
    ) -> None:
        unknown = set(schema.keys()) - self.SUPPORTED_KEYWORDS

        if unknown:
            names = ", ".join(sorted(str(item) for item in unknown))
            raise SchemaDefinitionError(
                f"Unsupported schema keyword(s) at {path}: {names}"
            )

        if "$ref" in schema:
            ref = schema["$ref"]
            if not isinstance(ref, str) or not ref:
                raise SchemaDefinitionError(
                    f"$ref at {path} must be a non-empty string"
                )
            if not ref.startswith("#/"):
                raise SchemaDefinitionError(
                    f"Only local JSON Pointer $ref is supported at {path}"
                )

        if "type" in schema:
            schema_type = schema["type"]
            types = (
                schema_type
                if isinstance(schema_type, list)
                else [schema_type]
            )

            if not types or any(
                item not in self.SUPPORTED_TYPES
                for item in types
            ):
                raise SchemaDefinitionError(
                    f"Unsupported type declaration at {path}"
                )

        if "properties" in schema:
            properties = schema["properties"]
            if not isinstance(properties, Mapping):
                raise SchemaDefinitionError(
                    f"properties at {path} must be an object"
                )

            for key, child in properties.items():
                if not isinstance(child, Mapping):
                    raise SchemaDefinitionError(
                        f"Property schema at {path}/{key} must be an object"
                    )
                self._check_schema_node(child, f"{path}/properties/{key}")

        if "items" in schema:
            items = schema["items"]
            if not isinstance(items, Mapping):
                raise SchemaDefinitionError(
                    f"items at {path} must be an object schema"
                )
            self._check_schema_node(items, f"{path}/items")

        if "additionalProperties" in schema:
            additional = schema["additionalProperties"]
            if isinstance(additional, Mapping):
                self._check_schema_node(
                    additional,
                    f"{path}/additionalProperties",
                )
            elif not isinstance(additional, bool):
                raise SchemaDefinitionError(
                    f"additionalProperties at {path} must be boolean or schema"
                )

        for keyword in ("anyOf", "allOf", "oneOf"):
            if keyword in schema:
                alternatives = schema[keyword]

                if (
                    not isinstance(alternatives, list)
                    or not alternatives
                ):
                    raise SchemaDefinitionError(
                        f"{keyword} at {path} must be a non-empty array"
                    )

                for index, child in enumerate(alternatives):
                    if not isinstance(child, Mapping):
                        raise SchemaDefinitionError(
                            f"{keyword} entry at {path}/{index} must be an object"
                        )
                    self._check_schema_node(
                        child,
                        f"{path}/{keyword}/{index}",
                    )

        if "not" in schema:
            if not isinstance(schema["not"], Mapping):
                raise SchemaDefinitionError(
                    f"not at {path} must be an object"
                )
            self._check_schema_node(schema["not"], f"{path}/not")

        if "required" in schema:
            required = schema["required"]

            if (
                not isinstance(required, list)
                or any(not isinstance(item, str) for item in required)
            ):
                raise SchemaDefinitionError(
                    f"required at {path} must be an array of strings"
                )

        if "format" in schema:
            if schema["format"] not in self.SUPPORTED_FORMATS:
                raise SchemaDefinitionError(
                    f"Unsupported format at {path}: {schema['format']}"
                )

        if "pattern" in schema:
            try:
                re.compile(schema["pattern"])
            except (TypeError, re.error) as exc:
                raise SchemaDefinitionError(
                    f"Invalid regular expression at {path}: {exc}"
                ) from exc

    # ---------------------------------------------------------
    # Public validation API
    # ---------------------------------------------------------

    def validate(
        self,
        instance: Any,
        schema_name: str,
    ) -> ValidationResult:
        """Validate an instance and return a structured result."""

        normalized = self.normalize_schema_name(schema_name)
        schema = self.load_schema(normalized)

        issues: list[ValidationIssue] = []

        self._validate_node(
            instance=instance,
            schema=schema,
            path="$",
            root_schema=schema,
            issues=issues,
            ref_stack=(),
        )

        return ValidationResult(
            valid=not issues,
            schema_name=normalized,
            issues=tuple(issues),
        )

    def validate_or_raise(
        self,
        instance: Any,
        schema_name: str,
    ) -> ValidationResult:
        """Validate an instance and raise SchemaValidationError on failure."""

        result = self.validate(instance, schema_name)

        if not result.valid:
            raise SchemaValidationError(
                schema_name=result.schema_name,
                issues=list(result.issues),
            )

        return result

    # ---------------------------------------------------------
    # Internal validation helpers
    # ---------------------------------------------------------

    def _add_issue(
        self,
        issues: list[ValidationIssue],
        path: str,
        message: str,
        keyword: str | None = None,
    ) -> None:
        if len(issues) >= self.max_errors:
            return

        issues.append(
            ValidationIssue(
                path=path,
                message=message,
                keyword=keyword,
            )
        )

    @staticmethod
    def _child_path(parent: str, key: str | int) -> str:
        if isinstance(key, int):
            return f"{parent}[{key}]"

        escaped = str(key).replace("~", "~0").replace("/", "~1")
        return f"{parent}.{escaped}"

    @staticmethod
    def _matches_type(value: Any, expected: str) -> bool:
        if expected == "object":
            return isinstance(value, dict)

        if expected == "array":
            return isinstance(value, list)

        if expected == "string":
            return isinstance(value, str)

        if expected == "integer":
            return isinstance(value, int) and not isinstance(value, bool)

        if expected == "number":
            return (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
            )

        if expected == "boolean":
            return isinstance(value, bool)

        if expected == "null":
            return value is None

        return False

    def _resolve_pointer(
        self,
        root_schema: Mapping[str, Any],
        ref: str,
    ) -> Mapping[str, Any]:
        """Resolve a local JSON Pointer such as #/definitions/example."""

        if not ref.startswith("#/"):
            raise SchemaDefinitionError(
                f"Unsupported reference: {ref}"
            )

        current: Any = root_schema
        tokens = ref[2:].split("/")

        for token in tokens:
            token = token.replace("~1", "/").replace("~0", "~")

            if isinstance(current, Mapping) and token in current:
                current = current[token]
            else:
                raise SchemaDefinitionError(
                    f"Unresolvable local reference: {ref}"
                )

        if not isinstance(current, Mapping):
            raise SchemaDefinitionError(
                f"Reference does not point to a schema object: {ref}"
            )

        return current

    @staticmethod
    def _is_valid_format(value: str, format_name: str) -> bool:
        try:
            if format_name == "date":
                date.fromisoformat(value)
                return True

            if format_name == "date-time":
                normalized = value.replace("Z", "+00:00")
                datetime.fromisoformat(normalized)
                return True

            if format_name == "time":
                normalized = value.replace("Z", "+00:00")
                time.fromisoformat(normalized)
                return True

            if format_name == "email":
                if len(value) > 254 or value.count("@") != 1:
                    return False

                local, domain = value.rsplit("@", 1)

                return bool(
                    local
                    and domain
                    and "." in domain
                    and not domain.startswith(".")
                    and not domain.endswith(".")
                )

            if format_name == "uri":
                parsed = urlparse(value)
                return bool(parsed.scheme and parsed.netloc)

        except (ValueError, TypeError):
            return False

        return False
    def _validate_node(
        self,
        instance: Any,
        schema: Mapping[str, Any],
        path: str,
        root_schema: Mapping[str, Any],
        issues: list[ValidationIssue],
        ref_stack: tuple[str, ...],
    ) -> None:
        if len(issues) >= self.max_errors:
            return

        # -----------------------------------------------------
        # Local reference
        # -----------------------------------------------------

        if "$ref" in schema:
            ref = schema["$ref"]

            if ref in ref_stack:
                self._add_issue(
                    issues,
                    path,
                    f"Circular schema reference detected: {ref}",
                    "$ref",
                )
                return

            referenced = self._resolve_pointer(root_schema, ref)

            self._validate_node(
                instance=instance,
                schema=referenced,
                path=path,
                root_schema=root_schema,
                issues=issues,
                ref_stack=ref_stack + (ref,),
            )

        # -----------------------------------------------------
        # Type
        # -----------------------------------------------------

        if "type" in schema:
            expected = schema["type"]
            expected_types = (
                expected if isinstance(expected, list) else [expected]
            )

            if not any(
                self._matches_type(instance, item)
                for item in expected_types
            ):
                self._add_issue(
                    issues,
                    path,
                    (
                        f"Expected type {expected_types}, "
                        f"got {type(instance).__name__}"
                    ),
                    "type",
                )
                return

        # -----------------------------------------------------
        # Enum and const
        # -----------------------------------------------------

        if "enum" in schema and instance not in schema["enum"]:
            self._add_issue(
                issues,
                path,
                f"Value must be one of {schema['enum']}",
                "enum",
            )

        if "const" in schema and instance != schema["const"]:
            self._add_issue(
                issues,
                path,
                f"Value must equal {schema['const']!r}",
                "const",
            )

        # -----------------------------------------------------
        # String validation
        # -----------------------------------------------------

        if isinstance(instance, str):
            if (
                "minLength" in schema
                and len(instance) < schema["minLength"]
            ):
                self._add_issue(
                    issues,
                    path,
                    f"String length must be >= {schema['minLength']}",
                    "minLength",
                )

            if (
                "maxLength" in schema
                and len(instance) > schema["maxLength"]
            ):
                self._add_issue(
                    issues,
                    path,
                    f"String length must be <= {schema['maxLength']}",
                    "maxLength",
                )

            if "pattern" in schema:
                if re.search(schema["pattern"], instance) is None:
                    self._add_issue(
                        issues,
                        path,
                        f"String does not match pattern {schema['pattern']!r}",
                        "pattern",
                    )

            if "format" in schema:
                format_name = schema["format"]

                if not self._is_valid_format(instance, format_name):
                    self._add_issue(
                        issues,
                        path,
                        f"Invalid {format_name} value",
                        "format",
                    )

        # -----------------------------------------------------
        # Numeric validation
        # -----------------------------------------------------

        if (
            isinstance(instance, (int, float))
            and not isinstance(instance, bool)
            and math.isfinite(instance)
        ):
            numeric_rules = (
                ("minimum", lambda value, limit: value >= limit),
                ("maximum", lambda value, limit: value <= limit),
                (
                    "exclusiveMinimum",
                    lambda value, limit: value > limit,
                ),
                (
                    "exclusiveMaximum",
                    lambda value, limit: value < limit,
                ),
            )

            for keyword, comparator in numeric_rules:
                if keyword in schema:
                    limit = schema[keyword]

                    if not comparator(instance, limit):
                        self._add_issue(
                            issues,
                            path,
                            f"Value violates {keyword}={limit}",
                            keyword,
                        )

        # -----------------------------------------------------
        # Object validation
        # -----------------------------------------------------

        if isinstance(instance, dict):
            required = schema.get("required", [])

            for key in required:
                if key not in instance:
                    self._add_issue(
                        issues,
                        self._child_path(path, key),
                        f"Required property '{key}' is missing",
                        "required",
                    )

            properties = schema.get("properties", {})
            additional = schema.get("additionalProperties", True)

            if (
                "minProperties" in schema
                and len(instance) < schema["minProperties"]
            ):
                self._add_issue(
                    issues,
                    path,
                    f"Object must contain at least {schema['minProperties']} properties",
                    "minProperties",
                )

            if (
                "maxProperties" in schema
                and len(instance) > schema["maxProperties"]
            ):
                self._add_issue(
                    issues,
                    path,
                    f"Object must contain at most {schema['maxProperties']} properties",
                    "maxProperties",
                )

            for key, value in instance.items():
                child_path = self._child_path(path, key)

                if key in properties:
                    self._validate_node(
                        instance=value,
                        schema=properties[key],
                        path=child_path,
                        root_schema=root_schema,
                        issues=issues,
                        ref_stack=ref_stack,
                    )
                    continue

                if additional is False:
                    self._add_issue(
                        issues,
                        child_path,
                        f"Additional property '{key}' is not allowed",
                        "additionalProperties",
                    )
                elif isinstance(additional, Mapping):
                    self._validate_node(
                        instance=value,
                        schema=additional,
                        path=child_path,
                        root_schema=root_schema,
                        issues=issues,
                        ref_stack=ref_stack,
                    )

        # -----------------------------------------------------
        # Array validation
        # -----------------------------------------------------

        if isinstance(instance, list):
            if (
                "minItems" in schema
                and len(instance) < schema["minItems"]
            ):
                self._add_issue(
                    issues,
                    path,
                    f"Array must contain at least {schema['minItems']} items",
                    "minItems",
                )

            if (
                "maxItems" in schema
                and len(instance) > schema["maxItems"]
            ):
                self._add_issue(
                    issues,
                    path,
                    f"Array must contain at most {schema['maxItems']} items",
                    "maxItems",
                )

            if schema.get("uniqueItems") is True:
                for index, value in enumerate(instance):
                    if value in instance[:index]:
                        self._add_issue(
                            issues,
                            self._child_path(path, index),
                            "Array items must be unique",
                            "uniqueItems",
                        )

            if "items" in schema:
                item_schema = schema["items"]

                for index, value in enumerate(instance):
                    self._validate_node(
                        instance=value,
                        schema=item_schema,
                        path=self._child_path(path, index),
                        root_schema=root_schema,
                        issues=issues,
                        ref_stack=ref_stack,
                    )

        # -----------------------------------------------------
        # Composition keywords
        # -----------------------------------------------------

        if "allOf" in schema:
            for child_schema in schema["allOf"]:
                self._validate_node(
                    instance=instance,
                    schema=child_schema,
                    path=path,
                    root_schema=root_schema,
                    issues=issues,
                    ref_stack=ref_stack,
                )

        if "anyOf" in schema:
            matched = False

            for child_schema in schema["anyOf"]:
                temporary: list[ValidationIssue] = []

                self._validate_node(
                    instance=instance,
                    schema=child_schema,
                    path=path,
                    root_schema=root_schema,
                    issues=temporary,
                    ref_stack=ref_stack,
                )

                if not temporary:
                    matched = True
                    break

            if not matched:
                self._add_issue(
                    issues,
                    path,
                    "Value does not match any anyOf schema",
                    "anyOf",
                )

        if "oneOf" in schema:
            match_count = 0

            for child_schema in schema["oneOf"]:
                temporary = []

                self._validate_node(
                    instance=instance,
                    schema=child_schema,
                    path=path,
                    root_schema=root_schema,
                    issues=temporary,
                    ref_stack=ref_stack,
                )

                if not temporary:
                    match_count += 1

            if match_count != 1:
                self._add_issue(
                    issues,
                    path,
                    (
                        "Value must match exactly one oneOf schema; "
                        f"matched {match_count}"
                    ),
                    "oneOf",
                )

        if "not" in schema:
            temporary = []

            self._validate_node(
                instance=instance,
                schema=schema["not"],
                path=path,
                root_schema=root_schema,
                issues=temporary,
                ref_stack=ref_stack,
            )

            if not temporary:
                self._add_issue(
                    issues,
                    path,
                    "Value must not match the not schema",
                    "not",
                )