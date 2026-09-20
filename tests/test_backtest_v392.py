import pandas as pd
from backtest.returns import calculate_forward_returns
from backtest.costs import TransactionCostModel
from backtest.alpha_backtest import AlphaBacktester


def panel():
    dates = pd.bdate_range("2025-01-02", periods=30)
    codes = ["600000", "600001", "600002", "600003"]
    rows = []
    for i, d in enumerate(dates):
        for j, c in enumerate(codes):
            o = 10 + j + i * .02
            rows.append({"date": d, "code": c, "open": o, "close": o * (1 + .002 * (j + 1)),
                         "volume": 1e6, "amount": o * 1e6,
                         "is_tradeable": True, "limit_up": False, "limit_down": False})
    return pd.DataFrame(rows)


def test_forward():
    df = panel()
    assert len(calculate_forward_returns(df, 1)) == len(df)


def test_cost():
    assert TransactionCostModel().calculate(100000, 50000)["total_cost"] > 0


def test_backtest():
    df = panel()
    alpha = lambda x: x.code.map({"600000": 4, "600001": 3, "600002": 2, "600003": 1})
    r = AlphaBacktester({"initial_capital": 1e6, "portfolio_size": 2}, {}).run(alpha, df)
    assert r.trading_days > 0 and r.final_capital > 0 and r.total_cost >= 0
