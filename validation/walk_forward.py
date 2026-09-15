"""V3.9.1 walk-forward rolling splits."""
from __future__ import annotations


def rolling_splits(
    dates,
    train: int = 252,
    val: int = 63,
    test: int = 63,
    step: int = 63,
):
    """按时间顺序滚动切分 (train_idx, val_idx, test_idx)。"""
    n = len(dates)
    splits = []
    start = 0
    while start + train + val + test <= n:
        train_idx = list(range(start, start + train))
        val_idx = list(range(start + train, start + train + val))
        test_idx = list(range(start + train + val, start + train + val + test))
        splits.append((train_idx, val_idx, test_idx))
        start += step
    return splits
