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
