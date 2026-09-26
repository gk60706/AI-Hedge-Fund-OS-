"""回测系统：V1.8 Walk Forward 切分与绩效评价；V3.5 Portfolio Backtest & Stress Test Engine。"""


# ============================================================================
# V3.9.2 Backtest Returns Engine exports
# ============================================================================

from .returns import (
    ForwardReturnConfigV392,
    ForwardReturnResultV392,
    ForwardReturnEngineV392,
    calculate_forward_returns_v392,
    calculate_multi_horizon_returns_v392,
    calculate_open_to_open_return_v392,
    calculate_close_to_close_return_v392,
    calculate_excess_return_v392,
    calculate_quantile_returns_v392,
    calculate_long_only_quantile_return_v392,
    prepare_alpha_dataset_v392,
)

__all__ = [
    "ForwardReturnConfigV392",
    "ForwardReturnResultV392",
    "ForwardReturnEngineV392",
    "calculate_forward_returns_v392",
    "calculate_multi_horizon_returns_v392",
    "calculate_open_to_open_return_v392",
    "calculate_close_to_close_return_v392",
    "calculate_excess_return_v392",
    "calculate_quantile_returns_v392",
    "calculate_long_only_quantile_return_v392",
    "prepare_alpha_dataset_v392",
]
