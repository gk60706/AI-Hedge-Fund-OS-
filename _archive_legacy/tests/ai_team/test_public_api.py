"""Public API surface of the ``ai_team`` package (PEP 562 lazy exports)."""

from __future__ import annotations

import ai_team


def test_hard_timeout_error_public_import():
    from ai_team import HardTimeoutNotSupportedError

    assert issubclass(HardTimeoutNotSupportedError, RuntimeError)


def test_hard_timeout_error_in_all():
    assert "HardTimeoutNotSupportedError" in ai_team.__all__


def test_all_lazy_exports_resolve():
    for name in ai_team._LAZY_EXPORTS:
        assert getattr(ai_team, name) is not None, name
