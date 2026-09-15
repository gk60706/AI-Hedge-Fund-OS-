"""V3.9.1 core tests: canonicalization / limit rules / walk-forward."""
from __future__ import annotations

import pandas as pd

from alpha.canonical import signature
from alpha.expression import AlphaExpressionV391
from market.limit_rules import limit_pct
from validation.walk_forward import rolling_splits


def test_canonical_commutative_signature_equal():
    a = AlphaExpressionV391(
        operator="add",
        children=[
            AlphaExpressionV391(feature="value"),
            AlphaExpressionV391(feature="momentum"),
        ],
    )
    b = AlphaExpressionV391(
        operator="add",
        children=[
            AlphaExpressionV391(feature="momentum"),
            AlphaExpressionV391(feature="value"),
        ],
    )
    assert signature(a) == signature(b)


def test_limit_pct_by_code_prefix():
    assert limit_pct("300394") == 0.20
    assert limit_pct("600000") == 0.10


def test_rolling_splits_sizes():
    dates = pd.bdate_range("2020-01-01", periods=400)
    splits = rolling_splits(
        dates,
        train=100,
        val=30,
        test=30,
        step=60,
    )
    assert len(splits) > 0
    for train_idx, val_idx, test_idx in splits:
        assert len(train_idx) == 100
        assert len(val_idx) == 30
        assert len(test_idx) == 30
