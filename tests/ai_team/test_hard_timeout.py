"""Tests for process-based hard timeout in the V3.10 research pipeline."""

from __future__ import annotations

import multiprocessing
import time

import pytest

from ai_team.research_pipeline import (
    AgentTimeoutError,
    HardTimeoutNotSupportedError,
    V310ResearchPipeline,
)


# Module-level callables are required by multiprocessing spawn.


def slow_callable():
    time.sleep(10)
    return "finished"


def normal_callable():
    return {
        "status": "ok",
        "count": 3,
        "items": ["a", "b", "c"],
    }


def runtime_error_callable():
    raise RuntimeError("simulated worker failure")


def test_process_timeout_terminates_slow_callable():
    timeout_seconds = 1.0
    started = time.monotonic()

    with pytest.raises(AgentTimeoutError):
        V310ResearchPipeline._call_with_timeout(
            slow_callable,
            timeout_seconds,
            "slow test",
            timeout_mode="process",
        )

    elapsed = time.monotonic() - started

    assert elapsed < timeout_seconds + 1.5
    assert all(not child.is_alive() for child in multiprocessing.active_children())


def test_process_mode_returns_normal_result():
    expected = {
        "status": "ok",
        "count": 3,
        "items": ["a", "b", "c"],
    }

    result = V310ResearchPipeline._call_with_timeout(
        normal_callable,
        5.0,
        "normal test",
        timeout_mode="process",
    )

    assert result == expected


def test_process_mode_propagates_runtime_error():
    with pytest.raises(RuntimeError, match="simulated worker failure"):
        V310ResearchPipeline._call_with_timeout(
            runtime_error_callable,
            5.0,
            "runtime error test",
            timeout_mode="process",
        )


def test_process_mode_rejects_unpickleable_callable():
    unpickleable_callable = lambda: "not pickleable"  # noqa: E731

    with pytest.raises(HardTimeoutNotSupportedError):
        V310ResearchPipeline._call_with_timeout(
            unpickleable_callable,
            5.0,
            "unpickleable test",
            timeout_mode="process",
        )
