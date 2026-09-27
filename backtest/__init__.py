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


# ============================================================================
# V3.9.2 Backtest Costs Engine exports
# ============================================================================

from .costs import (
    TradeSideV392,
    TransactionCostConfigV392,
    TradeCostResultV392,
    TransactionCostEngineV392,
    CostSummaryV392,
    calculate_transaction_costs_v392,
    calculate_turnover_cost_v392,
    apply_transaction_cost_v392,
    apply_transaction_cost_compounded_v392,
    summarize_costs_v392,
    cost_impact_analysis_v392,
)


# ============================================================================
# V3.9.2 Alpha Backtest exports
# ============================================================================

from .alpha_backtest import (
    AlphaBacktestConfigV392,
    AlphaDailyMetricsV392,
    AlphaBacktestResultV392,
    AlphaBacktestEngineV392,
    calculate_daily_ic_v392,
    add_signal_quantiles_v392,
    calculate_daily_quantile_returns_v392,
    calculate_daily_turnover_v392,
    calculate_equity_curve_v392,
    calculate_max_drawdown_v392,
    calculate_sharpe_v392,
    calculate_annualized_return_v392,
    calculate_annualized_volatility_v392,
    run_alpha_backtest_v392,
    alpha_result_to_dict_v392,
)
