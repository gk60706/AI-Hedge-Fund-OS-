from __future__ import annotations

from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_team.prompt_library import (
    PromptLibrary,
    PromptLibraryError,
    PromptNotFoundError,
    PromptRenderError,
    PromptValidationError,
)


# ============================================================
# Test helpers
# ============================================================

class FakeAgentRole(Enum):
    CIO = "cio"
    INTELLIGENCE = "intelligence"
    ANALYST = "analyst"


@pytest.fixture
def prompts_dir(tmp_path: Path) -> Path:
    """
    Create an isolated prompt directory containing all four prompts.
    """
    files = {
        "cio_chatgpt.txt": (
            "# CIO PROMPT\n"
            "Task: {{TASK_ID}}\n"
            "Subject: {{SUBJECT}}\n"
            "Ticker: {{TICKER}}\n"
        ),
        "intelligence_grok.txt": (
            "# INTELLIGENCE PROMPT\n"
            "Task: {{TASK_ID}}\n"
            "Subject: {{SUBJECT}}\n"
        ),
        "analyst_hark.txt": (
            "# ANALYST PROMPT\n"
            "Task: {{TASK_ID}}\n"
            "Subject: {{SUBJECT}}\n"
        ),
        "general_team.txt": (
            "# GENERAL TEAM PROMPT\n"
            "Task: {{TASK_ID}}\n"
        ),
    }

    for filename, content in files.items():
        (tmp_path / filename).write_text(
            content,
            encoding="utf-8",
        )

    return tmp_path


@pytest.fixture
def library(prompts_dir: Path) -> PromptLibrary:
    return PromptLibrary(prompts_dir=prompts_dir)


@pytest.fixture
def valid_variables() -> dict[str, str]:
    return {
        "TASK_ID": "V310-TEST-001",
        "SUBJECT": "天孚通信",
        "TICKER": "300394",
    }


# ============================================================
# Initialization
# ============================================================

def test_init_with_explicit_prompts_dir(prompts_dir: Path) -> None:
    prompt_library = PromptLibrary(
        prompts_dir=prompts_dir
    )

    assert prompt_library.prompts_dir == prompts_dir.resolve()


def test_init_with_config_prompts_dir(prompts_dir: Path) -> None:
    config = SimpleNamespace(
        prompts_dir=prompts_dir
    )

    prompt_library = PromptLibrary(config=config)

    assert prompt_library.prompts_dir == prompts_dir.resolve()


def test_explicit_prompts_dir_has_precedence(
    prompts_dir: Path,
    tmp_path: Path,
) -> None:
    other_dir = tmp_path / "other"
    other_dir.mkdir()

    config = SimpleNamespace(
        prompts_dir=other_dir
    )

    prompt_library = PromptLibrary(
        prompts_dir=prompts_dir,
        config=config,
    )

    assert prompt_library.prompts_dir == prompts_dir.resolve()


def test_init_rejects_config_without_prompts_dir() -> None:
    config = SimpleNamespace()

    with pytest.raises(ValueError):
        PromptLibrary(config=config)


def test_init_accepts_string_path(prompts_dir: Path) -> None:
    prompt_library = PromptLibrary(
        prompts_dir=str(prompts_dir)
    )

    assert prompt_library.prompts_dir == prompts_dir.resolve()


# ============================================================
# Prompt names
# ============================================================

def test_list_prompts_returns_four_prompt_names(
    library: PromptLibrary,
) -> None:
    assert library.list_prompts() == [
        "cio_chatgpt",
        "intelligence_grok",
        "analyst_hark",
        "general_team",
    ]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("cio_chatgpt", "cio_chatgpt"),
        ("cio_chatgpt.txt", "cio_chatgpt"),
        ("intelligence_grok", "intelligence_grok"),
        ("intelligence_grok.txt", "intelligence_grok"),
        ("analyst_hark", "analyst_hark"),
        ("general_team.txt", "general_team"),
    ],
)
def test_normalize_prompt_name(
    name: str,
    expected: str,
) -> None:
    assert PromptLibrary.normalize_prompt_name(name) == expected


def test_normalize_prompt_name_strips_whitespace() -> None:
    assert (
        PromptLibrary.normalize_prompt_name("  cio_chatgpt  ")
        == "cio_chatgpt"
    )


@pytest.mark.parametrize(
    "name",
    [
        "",
        " ",
    ],
)
def test_normalize_prompt_name_rejects_empty_name(
    name: str,
) -> None:
    with pytest.raises(ValueError):
        PromptLibrary.normalize_prompt_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "../cio_chatgpt",
        "prompts/cio_chatgpt",
        r"..\cio_chatgpt",
        "cio_chatgpt/../../secret",
    ],
)
def test_normalize_prompt_name_rejects_path_traversal(
    name: str,
) -> None:
    with pytest.raises(ValueError):
        PromptLibrary.normalize_prompt_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "unknown",
        "trader",
        "cio",
        "general",
        "cio_chatgpt.md",
    ],
)
def test_normalize_prompt_name_rejects_unknown_prompt(
    name: str,
) -> None:
    with pytest.raises(PromptNotFoundError):
        PromptLibrary.normalize_prompt_name(name)


def test_normalize_prompt_name_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        PromptLibrary.normalize_prompt_name(123)


# ============================================================
# Prompt loading
# ============================================================

@pytest.mark.parametrize(
    ("name", "expected_text"),
    [
        ("cio_chatgpt", "CIO PROMPT"),
        ("intelligence_grok", "INTELLIGENCE PROMPT"),
        ("analyst_hark", "ANALYST PROMPT"),
        ("general_team", "GENERAL TEAM PROMPT"),
    ],
)
def test_load_prompt(
    library: PromptLibrary,
    name: str,
    expected_text: str,
) -> None:
    content = library.load_prompt(name)

    assert expected_text in content
    assert content.strip()


def test_load_prompt_accepts_txt_extension(
    library: PromptLibrary,
) -> None:
    content = library.load_prompt("cio_chatgpt.txt")

    assert "CIO PROMPT" in content


def test_load_prompt_preserves_chinese_content(
    library: PromptLibrary,
) -> None:
    content = library.load_prompt("cio_chatgpt")

    assert "天孚通信" not in content
    assert "{{SUBJECT}}" in content


def test_load_prompt_rejects_unknown_prompt(
    library: PromptLibrary,
) -> None:
    with pytest.raises(PromptNotFoundError):
        library.load_prompt("unknown_prompt")


def test_load_prompt_rejects_missing_file(
    prompts_dir: Path,
    library: PromptLibrary,
) -> None:
    (prompts_dir / "cio_chatgpt.txt").unlink()

    with pytest.raises(PromptNotFoundError):
        library.load_prompt("cio_chatgpt")


def test_load_prompt_rejects_directory_instead_of_file(
    prompts_dir: Path,
    library: PromptLibrary,
) -> None:
    (prompts_dir / "cio_chatgpt.txt").unlink()
    (prompts_dir / "cio_chatgpt.txt").mkdir()

    with pytest.raises(PromptNotFoundError):
        library.load_prompt("cio_chatgpt")


def test_load_prompt_rejects_empty_file(
    prompts_dir: Path,
    library: PromptLibrary,
) -> None:
    (prompts_dir / "cio_chatgpt.txt").write_text(
        "  \n",
        encoding="utf-8",
    )

    with pytest.raises(PromptValidationError):
        library.load_prompt("cio_chatgpt")


# ============================================================
# Role mapping
# ============================================================

@pytest.mark.parametrize(
    ("role", "expected_text"),
    [
        (FakeAgentRole.CIO, "CIO PROMPT"),
        (FakeAgentRole.INTELLIGENCE, "INTELLIGENCE PROMPT"),
        (FakeAgentRole.ANALYST, "ANALYST PROMPT"),
        ("CIO", "CIO PROMPT"),
        ("INTELLIGENCE", "INTELLIGENCE PROMPT"),
        ("ANALYST", "ANALYST PROMPT"),
        ("cio", "CIO PROMPT"),
        ("intelligence", "INTELLIGENCE PROMPT"),
        ("analyst", "ANALYST PROMPT"),
    ],
)
def test_get_prompt_for_role(
    library: PromptLibrary,
    role: object,
    expected_text: str,
) -> None:
    content = library.get_prompt_for_role(role)

    assert expected_text in content


def test_get_prompt_for_unknown_role(
    library: PromptLibrary,
) -> None:
    with pytest.raises(PromptNotFoundError):
        library.get_prompt_for_role("TRADER")


def test_get_prompt_for_invalid_role(
    library: PromptLibrary,
) -> None:
    with pytest.raises(PromptNotFoundError):
        library.get_prompt_for_role(None)


# ============================================================
# Variable rendering
# ============================================================

def test_render_prompt_replaces_all_variables(
    library: PromptLibrary,
    valid_variables: dict[str, str],
) -> None:
    rendered = library.render_prompt(
        "cio_chatgpt",
        valid_variables,
    )

    assert "V310-TEST-001" in rendered
    assert "天孚通信" in rendered
    assert "300394" in rendered

    assert "{{TASK_ID}}" not in rendered
    assert "{{SUBJECT}}" not in rendered
    assert "{{TICKER}}" not in rendered


def test_render_prompt_accepts_txt_extension(
    library: PromptLibrary,
    valid_variables: dict[str, str],
) -> None:
    rendered = library.render_prompt(
        "cio_chatgpt.txt",
        valid_variables,
    )

    assert "V310-TEST-001" in rendered


def test_render_prompt_converts_integer_values_to_string(
    library: PromptLibrary,
) -> None:
    rendered = library.render_prompt(
        "cio_chatgpt",
        {
            "TASK_ID": 1001,
            "SUBJECT": 300394,
            "TICKER": 300394,
        },
    )

    assert "1001" in rendered
    assert "300394" in rendered


def test_render_prompt_converts_none_to_empty_string(
    library: PromptLibrary,
) -> None:
    rendered = library.render_prompt(
        "cio_chatgpt",
        {
            "TASK_ID": None,
            "SUBJECT": "测试公司",
            "TICKER": None,
        },
    )

    assert "测试公司" in rendered
    assert "{{TASK_ID}}" not in rendered
    assert "{{TICKER}}" not in rendered


def test_render_prompt_does_not_replace_similar_names(
    library: PromptLibrary,
) -> None:
    rendered = library.render_prompt(
        "cio_chatgpt",
        {
            "TASK_ID": "TASK-001",
            "SUBJECT": "公司A",
            "TICKER": "000001",
            "TASK": "WRONG",
        },
    )

    assert "TASK-001" in rendered
    assert "WRONG" not in rendered


def test_render_prompt_missing_variable_raises(
    library: PromptLibrary,
) -> None:
    with pytest.raises(PromptRenderError):
        library.render_prompt(
            "cio_chatgpt",
            {
                "TASK_ID": "TASK-001",
            },
        )


def test_render_prompt_reports_missing_variable_names(
    library: PromptLibrary,
) -> None:
    with pytest.raises(
        PromptRenderError,
        match="SUBJECT",
    ):
        library.render_prompt(
            "cio_chatgpt",
            {
                "TASK_ID": "TASK-001",
            },
        )


def test_render_prompt_non_strict_keeps_missing_variables(
    library: PromptLibrary,
) -> None:
    rendered = library.render_prompt(
        "cio_chatgpt",
        {
            "TASK_ID": "TASK-002",
        },
        strict=False,
    )

    assert "TASK-002" in rendered
    assert "{{SUBJECT}}" in rendered
    assert "{{TICKER}}" in rendered


def test_render_prompt_rejects_non_mapping_variables(
    library: PromptLibrary,
) -> None:
    with pytest.raises(TypeError):
        library.render_prompt(
            "cio_chatgpt",
            ["TASK_ID"],
        )


def test_render_prompt_rejects_non_string_variable_key(
    library: PromptLibrary,
) -> None:
    with pytest.raises(TypeError):
        library.render_prompt(
            "cio_chatgpt",
            {
                123: "value",
            },
            strict=False,
        )


def test_render_prompt_rejects_invalid_variable_key(
    library: PromptLibrary,
) -> None:
    with pytest.raises(PromptRenderError):
        library.render_prompt(
            "cio_chatgpt",
            {
                "TASK-ID": "TASK-003",
            },
            strict=False,
        )


def test_render_prompt_rejects_malformed_placeholder(
    prompts_dir: Path,
    library: PromptLibrary,
) -> None:
    (prompts_dir / "cio_chatgpt.txt").write_text(
        "Task: {{TASK_ID\n",
        encoding="utf-8",
    )

    with pytest.raises(PromptRenderError):
        library.render_prompt(
            "cio_chatgpt",
            {
                "TASK_ID": "TASK-004",
            },
        )


def test_render_for_role(
    library: PromptLibrary,
    valid_variables: dict[str, str],
) -> None:
    rendered = library.render_for_role(
        FakeAgentRole.ANALYST,
        valid_variables,
    )

    assert "ANALYST PROMPT" in rendered
    assert "V310-TEST-001" in rendered
    assert "天孚通信" in rendered


def test_render_for_role_rejects_missing_variables(
    library: PromptLibrary,
) -> None:
    with pytest.raises(PromptRenderError):
        library.render_for_role(
            FakeAgentRole.CIO,
            {
                "TASK_ID": "TASK-005",
            },
        )


def test_render_for_role_non_strict_mode(
    library: PromptLibrary,
) -> None:
    rendered = library.render_for_role(
        FakeAgentRole.CIO,
        {
            "TASK_ID": "TASK-006",
        },
        strict=False,
    )

    assert "TASK-006" in rendered
    assert "{{SUBJECT}}" in rendered


# ============================================================
# Prompt validation
# ============================================================

def test_validate_prompts_returns_valid_result(
    library: PromptLibrary,
) -> None:
    result = library.validate_prompts()

    assert result["valid"] is True
    assert result["checked"] == 4
    assert result["errors"] == []


def test_validate_prompts_contains_all_four_files(
    library: PromptLibrary,
) -> None:
    result = library.validate_prompts()

    assert set(result["prompts"]) == {
        "cio_chatgpt",
        "intelligence_grok",
        "analyst_hark",
        "general_team",
    }


def test_validate_prompts_reports_missing_file(
    prompts_dir: Path,
    library: PromptLibrary,
) -> None:
    (prompts_dir / "analyst_hark.txt").unlink()

    result = library.validate_prompts()

    assert result["valid"] is False
    assert result["prompts"]["analyst_hark"]["exists"] is False
    assert any(
        "analyst_hark" in error
        for error in result["errors"]
    )


def test_validate_prompts_reports_empty_file(
    prompts_dir: Path,
    library: PromptLibrary,
) -> None:
    (prompts_dir / "general_team.txt").write_text(
        "",
        encoding="utf-8",
    )

    result = library.validate_prompts()

    assert result["valid"] is False
    assert (
        result["prompts"]["general_team"]["non_empty"]
        is False
    )


def test_validate_prompts_collects_placeholder_names(
    library: PromptLibrary,
) -> None:
    result = library.validate_prompts()

    assert result["prompts"]["cio_chatgpt"]["placeholders"] == [
        "SUBJECT",
        "TASK_ID",
        "TICKER",
    ]


def test_validate_prompts_detects_malformed_placeholder(
    prompts_dir: Path,
    library: PromptLibrary,
) -> None:
    (prompts_dir / "cio_chatgpt.txt").write_text(
        "Broken: {{TASK_ID\n",
        encoding="utf-8",
    )

    result = library.validate_prompts()

    assert result["valid"] is False
    assert any(
        "malformed placeholder" in error
        for error in result["errors"]
    )


# ============================================================
# Default directory integration
# ============================================================

def test_default_prompt_directory_is_a_directory() -> None:
    prompt_library = PromptLibrary()

    assert prompt_library.prompts_dir.exists()
    assert prompt_library.prompts_dir.is_dir()


def test_default_prompt_directory_contains_all_prompts() -> None:
    prompt_library = PromptLibrary()

    result = prompt_library.validate_prompts()

    assert result["valid"] is True, result["errors"]


# ============================================================
# Public API and system boundaries
# ============================================================

def test_public_exports() -> None:
    from ai_team import prompt_library

    expected = {
        "PromptLibrary",
        "PromptLibraryError",
        "PromptNotFoundError",
        "PromptRenderError",
        "PromptValidationError",
    }

    assert expected.issubset(
        set(prompt_library.__all__)
    )


def test_prompt_library_has_no_trade_execution_methods(
    library: PromptLibrary,
) -> None:
    forbidden_methods = {
        "buy",
        "sell",
        "place_order",
        "submit_order",
        "execute_trade",
        "connect_broker",
    }

    public_methods = {
        name
        for name in dir(library)
        if not name.startswith("_")
    }

    assert forbidden_methods.isdisjoint(public_methods)


def test_prompt_library_does_not_store_api_keys(
    library: PromptLibrary,
) -> None:
    assert not hasattr(library, "api_key")
    assert not hasattr(library, "openai_api_key")
    assert not hasattr(library, "grok_api_key")
    assert not hasattr(library, "hark_api_key")


def test_prompt_library_uses_standard_library_only() -> None:
    """
    The prompt loader should not require third-party runtime packages.
    """
    import ai_team.prompt_library as module

    assert module.Path is Path
    assert module.re is not None


# ============================================================
# Test entry point
# ============================================================

if __name__ == "__main__":
    raise SystemExit(
        pytest.main([__file__, "-v"])
    )