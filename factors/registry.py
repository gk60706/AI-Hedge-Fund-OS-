from __future__ import annotations


class FactorRegistry:
    def __init__(
        self,
    ):
        self._factors = {}

    def register(
        self,
        factor,
    ):
        self._factors[factor.name] = factor

    def get(
        self,
        name: str,
    ):
        return self._factors.get(name)

    def all(
        self,
    ):
        return list(self._factors.values())
