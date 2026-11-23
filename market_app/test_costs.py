from __future__ import annotations

from market_app.costs import CostModel


def test_zero_cost_matches_gross():
    model = CostModel(
        commission_rate=0.0,
        min_commission=0.0,
        stamp_duty_rate=0.0,
        transfer_fee_rate=0.0,
        slippage_rate=0.0,
    )
    result = model.trade_return(100.0, 110.0)
    assert abs(result["gross_return_pct"] - 10.0) < 1e-9
    assert abs(result["net_return_pct"] - 10.0) < 1e-9
    assert result["total_fees"] == 0.0


def test_cost_reduces_net_return():
    model = CostModel()
    result = model.trade_return(100.0, 110.0)
    assert result["gross_return_pct"] == 10.0
    assert result["net_return_pct"] < result["gross_return_pct"]
    assert result["cost_drag_pct"] > 0
    assert result["buy_fees"] > 0
    assert result["sell_fees"] > result["buy_fees"]  # 卖出多了印花税


def test_min_commission_applies_to_small_trade():
    model = CostModel(capital=1000.0, commission_rate=0.00025, min_commission=5.0)
    result = model.trade_return(10.0, 10.0)
    # 1000 元本金的万 2.5 佣金只有 0.25 元，必须按最低 5 元收取。
    assert result["buy_commission"] == 5.0
    assert result["sell_commission"] == 5.0
    assert result["net_return_pct"] < 0


def test_slippage_moves_fill_prices():
    model = CostModel(slippage_rate=0.001)
    result = model.trade_return(100.0, 100.0)
    assert result["entry_fill"] > 100.0
    assert result["exit_fill"] < 100.0
    assert result["net_return_pct"] < 0


if __name__ == "__main__":
    test_zero_cost_matches_gross()
    test_cost_reduces_net_return()
    test_min_commission_applies_to_small_trade()
    test_slippage_moves_fill_prices()
    print("cost tests: PASS")
