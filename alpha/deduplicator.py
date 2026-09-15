from __future__ import annotations

import hashlib


class AlphaDeduplicator:
    def signature(self, expression):
        text = expression.to_string()
        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

    def deduplicate(self, expressions):
        seen = set()
        result = []
        for expression in expressions:
            signature = self.signature(expression)
            if signature in seen:
                continue
            seen.add(signature)
            result.append(expression)
        return result
# ============================================================================
# V3.9.1 unified research engine - canonical deduplicator (signal-aware)
# ============================================================================


class AlphaDeduplicatorV391:
    def __init__(self, correlation_threshold: float = 0.90):
        self.correlation_threshold = correlation_threshold
        self.signatures = set()
        self.signals = []

    def accept(self, expression, signal) -> bool:
        sig = signature(expression)
        if sig in self.signatures:
            return False
        for old_signal in self.signals:
            correlation = signal_correlation(signal, old_signal)
            if correlation == correlation and abs(correlation) >= self.correlation_threshold:
                return False
        self.signatures.add(sig)
        self.signals.append(signal)
        return True


from alpha.canonical import signature  # noqa: E402
from alpha.correlation import signal_correlation  # noqa: E402
