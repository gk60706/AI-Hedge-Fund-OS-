from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Optional


class PromptLibraryError(Exception):
    """Base exception for prompt library errors."""


class PromptNotFoundError(PromptLibraryError):
    """Raised when a prompt file does not exist."""


class PromptRenderError(PromptLibraryError):
    """Raised when prompt rendering fails."""


class PromptValidationError(PromptLibraryError):
    """Raised when a prompt file fails validation."""


class PromptLibrary:
    """
    Standard-library prompt loader for AI Hedge Fund OS V3.10.

    Default directory:
        ai_team/prompts/

    Supported placeholders:
        {{TASK_ID}}
        {{SUBJECT}}

    The loader does not call external AI services and does not require
    API credentials.
    """

    DEFAULT_PROMPTS = {
        "cio_chatgpt": "cio_chatgpt.txt",
        "intelligence_grok": "intelligence_grok.txt",
        "analyst_hark": "analyst_hark.txt",
        "general_team": "general_team.txt",
    }

    ROLE_PROMPTS = {
        "CIO": "cio_chatgpt",
        "INTELLIGENCE": "intelligence_grok",
        "ANALYST": "analyst_hark",
    }

    PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
    MALFORMED_OPEN_PATTERN = re.compile(r"\{\{")
    MALFORMED_CLOSE_PATTERN = re.compile(r"\}\}")

    def __init__(
        self,
        prompts_dir: Optional[str | Path] = None,
        config: Any = None,
        encoding: str = "utf-8",
    ) -> None:
        """
        Args:
            prompts_dir:
                Explicit prompt directory. Takes precedence over config.
            config:
                Optional Step 1 TeamConfig instance. Its prompts_dir
                property is used when prompts_dir is not supplied.
            encoding:
                Text encoding. Defaults to UTF-8.
        """
        self.encoding = encoding

        if prompts_dir is not None:
            resolved_dir = Path(prompts_dir)
        elif config is not None:
            config_dir = getattr(config, "prompts_dir", None)
            if config_dir is None:
                raise ValueError(
                    "config must expose a prompts_dir property"
                )
            resolved_dir = Path(config_dir)
        else:
            resolved_dir = self._get_default_prompts_dir()

        self.prompts_dir = resolved_dir.expanduser().resolve()

    @staticmethod
    def _get_default_prompts_dir() -> Path:
        """
        Resolve the default prompt directory through Step 1 configuration.

        A local fallback is retained for isolated tests and standalone use.
        """
        try:
            from ai_team.config import get_default_config

            config = get_default_config()
            config_dir = getattr(config, "prompts_dir", None)

            if config_dir is not None:
                return Path(config_dir)
        except ImportError:
            pass

        return Path(__file__).resolve().parent / "prompts"

    @classmethod
    def normalize_prompt_name(cls, name: str) -> str:
        """
        Normalize a prompt identifier.

        Accepts:
            cio_chatgpt
            cio_chatgpt.txt

        Arbitrary paths and path traversal are rejected.
        """
        if not isinstance(name, str):
            raise TypeError("prompt name must be a string")

        normalized = name.strip()

        if not normalized:
            raise ValueError("prompt name cannot be empty")

        if "/" in normalized or "\\" in normalized:
            raise ValueError("prompt name must not contain a path")

        if normalized.endswith(".txt"):
            normalized = normalized[:-4]

        if normalized not in cls.DEFAULT_PROMPTS:
            raise PromptNotFoundError(
                f"Unknown prompt name: {name}"
            )

        return normalized

    @classmethod
    def _role_name(cls, role: Any) -> str:
        """
        Convert a Step 1 AgentRole enum or string to its role name.
        """
        if hasattr(role, "name"):
            role_name = str(role.name)
        elif hasattr(role, "value"):
            role_name = str(role.value)
        else:
            role_name = str(role)

        role_name = role_name.strip().upper()

        if role_name not in cls.ROLE_PROMPTS:
            raise PromptNotFoundError(
                f"No prompt configured for role: {role_name}"
            )

        return role_name

    def _prompt_path(self, name: str) -> Path:
        normalized = self.normalize_prompt_name(name)
        filename = self.DEFAULT_PROMPTS[normalized]
        path = (self.prompts_dir / filename).resolve()

        # Defensive path containment check.
        if path.parent != self.prompts_dir:
            raise PromptNotFoundError(
                "Prompt path is outside the configured prompt directory"
            )

        return path

    def load_prompt(self, name: str) -> str:
        """
        Load a prompt as UTF-8 text.

        Args:
            name: Prompt identifier, with or without .txt suffix.

        Returns:
            Complete prompt content.
        """
        path = self._prompt_path(name)

        if not path.exists():
            raise PromptNotFoundError(
                f"Prompt file does not exist: {path}"
            )

        if not path.is_file():
            raise PromptNotFoundError(
                f"Prompt path is not a file: {path}"
            )

        try:
            content = path.read_text(encoding=self.encoding)
        except (OSError, UnicodeError) as exc:
            raise PromptLibraryError(
                f"Unable to read prompt file {path}: {exc}"
            ) from exc

        if not content.strip():
            raise PromptValidationError(
                f"Prompt file is empty: {path}"
            )

        return content

    def get_prompt_for_role(self, role: Any) -> str:
        """
        Load the prompt associated with a Step 1 AgentRole.

        Supported roles:
            AgentRole.CIO
            AgentRole.INTELLIGENCE
            AgentRole.ANALYST
        """
        role_name = self._role_name(role)
        prompt_name = self.ROLE_PROMPTS[role_name]
        return self.load_prompt(prompt_name)

    def render_prompt(
        self,
        name: str,
        variables: Optional[Mapping[str, Any]] = None,
        strict: bool = True,
    ) -> str:
        """
        Render {{VARIABLE_NAME}} placeholders.

        Args:
            name:
                Prompt identifier.
            variables:
                Mapping of placeholder names to values.
            strict:
                If True, missing placeholders raise PromptRenderError.
                If False, unresolved placeholders remain unchanged.

        Values are converted to strings. None becomes an empty string.
        """
        content = self.load_prompt(name)
        values = variables or {}

        if not isinstance(values, Mapping):
            raise TypeError("variables must be a mapping")

        normalized_values: dict[str, str] = {}

        for key, value in values.items():
            if not isinstance(key, str):
                raise TypeError("variable names must be strings")

            normalized_key = key.strip()

            if not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*",
                normalized_key,
            ):
                raise PromptRenderError(
                    f"Invalid variable name: {key!r}"
                )

            normalized_values[normalized_key] = (
                "" if value is None else str(value)
            )

        found_names = set(self.PLACEHOLDER_PATTERN.findall(content))

        if strict:
            missing = sorted(found_names - set(normalized_values))

            if missing:
                missing_text = ", ".join(missing)
                raise PromptRenderError(
                    f"Missing prompt variables: {missing_text}"
                )

        def replace_match(match: re.Match[str]) -> str:
            variable_name = match.group(1)

            if variable_name not in normalized_values:
                return match.group(0)

            return normalized_values[variable_name]

        rendered = self.PLACEHOLDER_PATTERN.sub(
            replace_match,
            content,
        )

        # Reject malformed opening braces rather than silently returning
        # a prompt with an accidentally broken placeholder.
        if self.MALFORMED_OPEN_PATTERN.search(rendered):
            if strict:
                raise PromptRenderError(
                    "Malformed or unresolved prompt placeholder"
                )

        return rendered

    def render_for_role(
        self,
        role: Any,
        variables: Optional[Mapping[str, Any]] = None,
        strict: bool = True,
    ) -> str:
        """
        Load and render a role-specific prompt.
        """
        role_name = self._role_name(role)
        prompt_name = self.ROLE_PROMPTS[role_name]

        return self.render_prompt(
            prompt_name,
            variables=variables,
            strict=strict,
        )

    def list_prompts(self) -> list[str]:
        """
        Return the known prompt identifiers in stable order.
        """
        return list(self.DEFAULT_PROMPTS.keys())

    def validate_prompts(self) -> dict[str, Any]:
        """
        Validate all configured prompt files.

        Returns:
            {
                "valid": bool,
                "checked": int,
                "errors": [...],
                "prompts": {
                    "cio_chatgpt": {
                        "exists": True,
                        "non_empty": True,
                        "placeholders": [...]
                    }
                }
            }
        """
        results: dict[str, Any] = {}
        errors: list[str] = []

        for prompt_name in self.DEFAULT_PROMPTS:
            filename = self.DEFAULT_PROMPTS[prompt_name]
            path = self.prompts_dir / filename

            item: dict[str, Any] = {
                "exists": path.is_file(),
                "non_empty": False,
                "placeholders": [],
            }

            if not path.is_file():
                errors.append(
                    f"{prompt_name}: missing file {filename}"
                )
                results[prompt_name] = item
                continue

            try:
                content = path.read_text(encoding=self.encoding)
            except (OSError, UnicodeError) as exc:
                errors.append(
                    f"{prompt_name}: unable to read file: {exc}"
                )
                results[prompt_name] = item
                continue

            item["non_empty"] = bool(content.strip())
            item["placeholders"] = sorted(
                set(self.PLACEHOLDER_PATTERN.findall(content))
            )

            if not item["non_empty"]:
                errors.append(
                    f"{prompt_name}: file is empty"
                )

            # Remove all valid placeholders. Any remaining opening {{
            # indicates a malformed placeholder.
            remainder = self.PLACEHOLDER_PATTERN.sub("", content)

            if self.MALFORMED_OPEN_PATTERN.search(remainder):
                errors.append(
                    f"{prompt_name}: malformed placeholder syntax"
                )

            results[prompt_name] = item

        return {
            "valid": not errors,
            "checked": len(self.DEFAULT_PROMPTS),
            "errors": errors,
            "prompts": results,
        }


__all__ = [
    "PromptLibrary",
    "PromptLibraryError",
    "PromptNotFoundError",
    "PromptRenderError",
    "PromptValidationError",
]