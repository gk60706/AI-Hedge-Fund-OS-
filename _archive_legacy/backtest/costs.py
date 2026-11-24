"""V3.6 TradingCostModel：交易成本模型（佣金最低 5 元 / 印花税 / 滑点）。"""

from __future__ import annotations


class TradingCostModel:
    def __init__(
        self,
        commission_rate=0.0003,
        stamp_duty_rate=0.0005,
        slippage_rate=0.0005,
        minimum_commission=5.0,
    ):
        self.commission_rate = commission_rate
        self.stamp_duty_rate = stamp_duty_rate
        self.slippage_rate = slippage_rate
        self.minimum_commission = minimum_commission

    def commission(self, value: float) -> float:
        if value <= 0:
            return 0.0
        return max(value * self.commission_rate, self.minimum_commission)

    def stamp_duty(self, sell_value: float) -> float:
        if sell_value <= 0:
            return 0.0
        return sell_value * self.stamp_duty_rate

    def buy_price(self, price: float) -> float:
        return price * (1 + self.slippage_rate)

    def sell_price(self, price: float) -> float:
        return price * (1 - self.slippage_rate)
# ============================================================================
# V3.9.1 unified research engine - transaction cost (notional, side, dump)
# ============================================================================


def transaction_cost(
    notional: float,
    side: str,
    commission_rate=0.0003,
    stamp_duty=0.0005,
    min_commission=5.0,
):
    notional = abs(float(notional))
    if notional <= 0:
        return 0.0
    commission = max(min_commission, notional * commission_rate)
    stamp = notional * stamp_duty if side.upper() == "SELL" else 0.0
    return commission + stamp


# ============================================================================
# V3.9.2 frozen TransactionCostModel + build_cost_model (Alpha Research Engine)
# ============================================================================
from dataclasses import dataclass


@dataclass(frozen=True)
class TransactionCostModel:
    commission_rate: float = 0.0003
    stamp_duty_rate: float = 0.0005
    transfer_fee_rate: float = 0.00001
    slippage_buy: float = 0.0005
    slippage_sell: float = 0.0005
    min_commission: float = 5.0

    def commission(self, value):
        value = max(float(value), 0)
        return 0.0 if value == 0 else max(value * self.commission_rate, self.min_commission)

    def stamp_duty(self, value):
        return max(float(value), 0) * self.stamp_duty_rate

    def transfer_fee(self, value):
        return max(float(value), 0) * self.transfer_fee_rate

    def slippage_cost(self, buy_value=0, sell_value=0):
        return max(float(buy_value), 0) * self.slippage_buy + max(float(sell_value), 0) * self.slippage_sell

    def calculate(self, buy_value=0, sell_value=0):
        b = max(float(buy_value), 0); s = max(float(sell_value), 0); t = b + s
        c = self.commission(t) if t else 0.0
        sd = self.stamp_duty(s); tf = self.transfer_fee(t); sl = self.slippage_cost(b, s)
        return {"buy_value": b, "sell_value": s, "turnover_value": t, "commission": c,
                "stamp_duty": sd, "transfer_fee": tf, "slippage": sl, "total_cost": c + sd + tf + sl}


def build_cost_model(config=None):
    c = config or {}; cm = c.get("commission", {}); sd = c.get("stamp_duty", {})
    tf = c.get("transfer_fee", {}); sl = c.get("slippage", {})
    return TransactionCostModel(
        float(cm.get("rate", .0003)),
        float(sd.get("sell_rate", .0005)),
        float(tf.get("rate", .00001)),
        float(sl.get("buy", .0005)),
        float(sl.get("sell", .0005)),
        float(cm.get("min_fee", 5)),
    )



# ============================================================================
# V3.9.2 A-Share Transaction Cost Engine (V392 suffix names)
# ============================================================================

import numpy as np
import pandas as pd
from typing import Optional
from enum import Enum


class TradeSideV392(str, Enum):
    """
    交易方向。
    """
    BUY = "buy"
    SELL = "sell"


@dataclass
class TransactionCostConfigV392:
    """
    A股交易成本配置。

    commission_rate:
        佣金费率。

    stamp_duty_rate:
        印花税率。

        默认只在卖出时收取。

    slippage_rate:
        滑点。

    min_commission:
        单笔最低佣金。

        研究型横截面回测通常可以设为 0，
        组合级回测则可以设置最低佣金。

    apply_stamp_duty_on_sell:
        是否卖出收取印花税。

    commission_on_buy:
        买入是否收佣金。

    commission_on_sell:
        卖出是否收佣金。
    """
    commission_rate: float = 0.0003
    stamp_duty_rate: float = 0.0005
    slippage_rate: float = 0.0005
    min_commission: float = 0.0
    apply_stamp_duty_on_sell: bool = True
    commission_on_buy: bool = True
    commission_on_sell: bool = True
    # 是否启用滑点
    apply_slippage: bool = True
    # 买入滑点方向：
    # buy  -> execution price higher
    # sell -> execution price lower
    directional_slippage: bool = True
    # 是否按成交金额计算
    use_notional: bool = True

    def validate(self) -> None:
        rates = {
            "commission_rate": self.commission_rate,
            "stamp_duty_rate": self.stamp_duty_rate,
            "slippage_rate": self.slippage_rate,
        }
        for name, value in rates.items():
            if value < 0:
                raise ValueError(
                    f"{name} must be >= 0"
                )
        if self.min_commission < 0:
            raise ValueError(
                "min_commission must be >= 0"
            )


@dataclass
class TradeCostResultV392:
    """
    单笔交易成本结果。
    """
    side: TradeSideV392
    quantity: float
    price: float
    notional: float
    commission: float
    stamp_duty: float
    slippage_cost: float
    total_cost: float
    cost_rate: float
    execution_price: float


class TransactionCostEngineV392:
    """
    交易成本计算引擎。
    """

    def __init__(
        self,
        config: Optional[TransactionCostConfigV392] = None,
    ):
        self.config = (
            config or TransactionCostConfigV392()
        )
        self.config.validate()

    # ========================================================
    # Commission
    # ========================================================
    def commission(
        self,
        notional: float,
        side: TradeSideV392,
    ) -> float:
        if notional <= 0:
            return 0.0
        if side == TradeSideV392.BUY:
            enabled = (
                self.config.commission_on_buy
            )
        else:
            enabled = (
                self.config.commission_on_sell
            )
        if not enabled:
            return 0.0
        value = (
            notional * self.config.commission_rate
        )
        if (
            self.config.min_commission > 0
            and value > 0
        ):
            value = max(
                value,
                self.config.min_commission,
            )
        return float(value)

    # ========================================================
    # Stamp Duty
    # ========================================================
    def stamp_duty(
        self,
        notional: float,
        side: TradeSideV392,
    ) -> float:
        if notional <= 0:
            return 0.0
        if side != TradeSideV392.SELL:
            return 0.0
        if not self.config.apply_stamp_duty_on_sell:
            return 0.0
        return float(
            notional * self.config.stamp_duty_rate
        )

    # ========================================================
    # Slippage
    # ========================================================
    def execution_price(
        self,
        price: float,
        side: TradeSideV392,
    ) -> float:
        if price <= 0:
            raise ValueError(
                "price must be > 0"
            )
        if not self.config.apply_slippage:
            return float(price)
        rate = (
            self.config.slippage_rate
        )
        if not self.config.directional_slippage:
            return float(price)
        if side == TradeSideV392.BUY:
            return float(
                price * (1.0 + rate)
            )
        return float(
            price * (1.0 - rate)
        )

    def slippage_cost(
        self,
        notional: float,
    ) -> float:
        if notional <= 0:
            return 0.0
        if not self.config.apply_slippage:
            return 0.0
        return float(
            notional * self.config.slippage_rate
        )

    # ========================================================
    # Single Trade
    # ========================================================
    def calculate_trade(
        self,
        price: float,
        quantity: float,
        side: TradeSideV392,
    ) -> TradeCostResultV392:
        if price <= 0:
            raise ValueError(
                "price must be > 0"
            )
        if quantity <= 0:
            raise ValueError(
                "quantity must be > 0"
            )
        notional = (
            price * quantity
        )
        commission = self.commission(
            notional,
            side,
        )
        stamp_duty = self.stamp_duty(
            notional,
            side,
        )
        slippage = self.slippage_cost(
            notional,
        )
        total_cost = (
            commission + stamp_duty + slippage
        )
        execution_price = (
            self.execution_price(
                price,
                side,
            )
        )
        cost_rate = (
            total_cost / notional
            if notional > 0
            else 0.0
        )
        return TradeCostResultV392(
            side=side,
            quantity=float(quantity),
            price=float(price),
            notional=float(notional),
            commission=float(commission),
            stamp_duty=float(stamp_duty),
            slippage_cost=float(slippage),
            total_cost=float(total_cost),
            cost_rate=float(cost_rate),
            execution_price=float(execution_price),
        )


# ============================================================
# Vectorized Cost Calculation
# ============================================================
def calculate_transaction_costs_v392(
    df: pd.DataFrame,
    price_column: str = "price",
    quantity_column: str = "quantity",
    side_column: str = "side",
    config: Optional[TransactionCostConfigV392] = None,
) -> pd.DataFrame:
    """
    批量计算交易成本。

    输入：

        date
        code
        price
        quantity
        side

    side:
        buy / sell

    输出：

        notional
        commission
        stamp_duty
        slippage_cost
        total_cost
        cost_rate
        execution_price
    """
    required = {
        price_column,
        quantity_column,
        side_column,
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            "Missing required columns: "
            f"{sorted(missing)}"
        )
    data = df.copy()
    engine = TransactionCostEngineV392(config)
    data[price_column] = pd.to_numeric(
        data[price_column],
        errors="coerce",
    )
    data[quantity_column] = pd.to_numeric(
        data[quantity_column],
        errors="coerce",
    )
    if (
        data[price_column].isna().any()
        or data[quantity_column].isna().any()
    ):
        raise ValueError(
            "Price or quantity contains "
            "invalid values."
        )
    data["_side"] = (
        data[side_column]
        .astype(str)
        .str
        .lower()
        .map(
            {
                "buy": TradeSideV392.BUY,
                "sell": TradeSideV392.SELL,
                "b": TradeSideV392.BUY,
                "s": TradeSideV392.SELL,
            }
        )
    )
    if data["_side"].isna().any():
        invalid = (
            data.loc[
                data["_side"].isna(),
                side_column,
            ]
            .unique()
            .tolist()
        )
        raise ValueError(
            "Invalid trade side: "
            f"{invalid}"
        )
    notionals = (
        data[price_column] * data[quantity_column]
    )
    data["notional"] = notionals
    data["commission"] = 0.0
    data["stamp_duty"] = 0.0
    data["slippage_cost"] = 0.0
    data["total_cost"] = 0.0
    data["cost_rate"] = 0.0
    data["execution_price"] = (
        data[price_column]
    )
    buy_mask = (
        data["_side"] == TradeSideV392.BUY
    )
    sell_mask = (
        data["_side"] == TradeSideV392.SELL
    )
    # --------------------------------------------------------
    # Commission
    # --------------------------------------------------------
    if engine.config.commission_on_buy:
        data.loc[
            buy_mask,
            "commission",
        ] = (
            data.loc[
                buy_mask,
                "notional",
            ]
            * engine.config.commission_rate
        )
    if engine.config.commission_on_sell:
        data.loc[
            sell_mask,
            "commission",
        ] = (
            data.loc[
                sell_mask,
                "notional",
            ]
            * engine.config.commission_rate
        )
    # Minimum commission
    if engine.config.min_commission > 0:
        commission_mask = (
            data["commission"] > 0
        )
        data.loc[
            commission_mask,
            "commission",
        ] = np.maximum(
            data.loc[
                commission_mask,
                "commission",
            ],
            engine.config.min_commission,
        )
    # --------------------------------------------------------
    # Stamp Duty
    # --------------------------------------------------------
    if (
        engine.config.apply_stamp_duty_on_sell
    ):
        data.loc[
            sell_mask,
            "stamp_duty",
        ] = (
            data.loc[
                sell_mask,
                "notional",
            ]
            * engine.config.stamp_duty_rate
        )
    # --------------------------------------------------------
    # Slippage
    # --------------------------------------------------------
    if engine.config.apply_slippage:
        data["slippage_cost"] = (
            data["notional"]
            * engine.config.slippage_rate
        )
        if engine.config.directional_slippage:
            data.loc[
                buy_mask,
                "execution_price",
            ] = (
                data.loc[
                    buy_mask,
                    price_column,
                ]
                * (
                    1.0
                    + engine.config.slippage_rate
                )
            )
            data.loc[
                sell_mask,
                "execution_price",
            ] = (
                data.loc[
                    sell_mask,
                    price_column,
                ]
                * (
                    1.0
                    - engine.config.slippage_rate
                )
            )
    # --------------------------------------------------------
    # Total
    # --------------------------------------------------------
    data["total_cost"] = (
        data["commission"]
        + data["stamp_duty"]
        + data["slippage_cost"]
    )
    data["cost_rate"] = np.where(
        data["notional"] > 0,
        data["total_cost"] / data["notional"],
        0.0,
    )
    data = data.drop(
        columns=[
            "_side"
        ]
    )
    return data


# ============================================================
# Turnover Cost
# ============================================================
def calculate_turnover_cost_v392(
    turnover: pd.Series,
    config: Optional[TransactionCostConfigV392] = None,
    buy_ratio: float = 0.5,
) -> pd.DataFrame:
    """
    根据组合换手率估算交易成本。

    turnover:
        组合日换手率。

    buy_ratio:
        换手中买入占比。

    默认：
        50% buy
        50% sell

    注意：
    这是组合研究层面的估算，
    不是订单级成本。
    """
    if not isinstance(turnover, pd.Series):
        raise TypeError(
            "turnover must be pandas.Series"
        )
    if not 0 <= buy_ratio <= 1:
        raise ValueError(
            "buy_ratio must be between 0 and 1"
        )
    cfg = (
        config or TransactionCostConfigV392()
    )
    cfg.validate()
    turnover = pd.to_numeric(
        turnover,
        errors="coerce",
    )
    buy_turnover = (
        turnover * buy_ratio
    )
    sell_turnover = (
        turnover * (1.0 - buy_ratio)
    )
    buy_cost_rate = (
        cfg.commission_rate + cfg.slippage_rate
    )
    sell_cost_rate = (
        cfg.commission_rate
        + cfg.stamp_duty_rate
        + cfg.slippage_rate
    )
    buy_cost = (
        buy_turnover * buy_cost_rate
    )
    sell_cost = (
        sell_turnover * sell_cost_rate
    )
    result = pd.DataFrame(
        {
            "turnover": turnover,
            "buy_turnover": buy_turnover,
            "sell_turnover": sell_turnover,
            "buy_cost": buy_cost,
            "sell_cost": sell_cost,
        }
    )
    result["total_cost"] = (
        result["buy_cost"] + result["sell_cost"]
    )
    result["cost_rate"] = np.where(
        turnover > 0,
        result["total_cost"] / turnover,
        0.0,
    )
    return result


# ============================================================
# Net Return
# ============================================================
def apply_transaction_cost_v392(
    gross_return: pd.Series,
    cost_rate: pd.Series | float,
) -> pd.Series:
    """
    从 Gross Return 中扣除交易成本。

    简化模型：

        net_return
        =
        gross_return - cost_rate

    """
    gross = pd.to_numeric(
        gross_return,
        errors="coerce",
    )
    cost = pd.to_numeric(
        cost_rate,
        errors="coerce",
    )
    return gross - cost


def apply_transaction_cost_compounded_v392(
    gross_return: pd.Series,
    cost_rate: pd.Series | float,
) -> pd.Series:
    """
    更严格的组合净收益计算。

    近似：

        net wealth
        =
        (1 + gross_return)
        *
        (1 - cost_rate)

    因此：

        net_return
        =
        (1 + gross_return)
        *
        (1 - cost_rate)
        - 1
    """
    gross = pd.to_numeric(
        gross_return,
        errors="coerce",
    )
    cost = pd.to_numeric(
        cost_rate,
        errors="coerce",
    )
    return (
        (
            1.0 + gross
        )
        * (
            1.0 - cost
        )
        - 1.0
    )


# ============================================================
# Cost Summary
# ============================================================
@dataclass
class CostSummaryV392:
    """
    成本汇总。
    """
    total_notional: float
    total_commission: float
    total_stamp_duty: float
    total_slippage: float
    total_cost: float
    total_cost_rate: float
    number_of_trades: int


def summarize_costs_v392(
    trades: pd.DataFrame,
) -> CostSummaryV392:
    """
    汇总交易成本。
    """
    required = {
        "notional",
        "commission",
        "stamp_duty",
        "slippage_cost",
        "total_cost",
    }
    missing = required - set(trades.columns)
    if missing:
        raise ValueError(
            "Missing cost columns: "
            f"{sorted(missing)}"
        )
    total_notional = float(
        trades["notional"].sum()
    )
    total_commission = float(
        trades["commission"].sum()
    )
    total_stamp_duty = float(
        trades["stamp_duty"].sum()
    )
    total_slippage = float(
        trades["slippage_cost"].sum()
    )
    total_cost = float(
        trades["total_cost"].sum()
    )
    total_cost_rate = (
        total_cost / total_notional
        if total_notional > 0
        else 0.0
    )
    return CostSummaryV392(
        total_notional=total_notional,
        total_commission=total_commission,
        total_stamp_duty=total_stamp_duty,
        total_slippage=total_slippage,
        total_cost=total_cost,
        total_cost_rate=float(total_cost_rate),
        number_of_trades=len(trades),
    )


# ============================================================
# Cost Impact Analysis
# ============================================================
def cost_impact_analysis_v392(
    gross_returns: pd.Series,
    cost_rates: pd.Series,
) -> pd.DataFrame:
    """
    分析交易成本对收益的影响。

    输出：

        gross_return
        cost_rate
        net_return
        cost_drag
    """
    gross = pd.to_numeric(
        gross_returns,
        errors="coerce",
    )
    costs = pd.to_numeric(
        cost_rates,
        errors="coerce",
    )
    result = pd.DataFrame(
        {
            "gross_return": gross,
            "cost_rate": costs,
        }
    )
    result["net_return"] = (
        result["gross_return"] - result["cost_rate"]
    )
    result["cost_drag"] = (
        result["gross_return"] - result["net_return"]
    )
    return result


# ============================================================
# Self Test
# ============================================================
def _self_test_v392() -> None:
    config = TransactionCostConfigV392(
        commission_rate=0.0003,
        stamp_duty_rate=0.0005,
        slippage_rate=0.0005,
    )
    engine = TransactionCostEngineV392(config)
    # --------------------------------------------------------
    # Buy
    # --------------------------------------------------------
    buy = engine.calculate_trade(
        price=10.0,
        quantity=1000,
        side=TradeSideV392.BUY,
    )
    assert np.isclose(buy.notional, 10000.0)
    assert np.isclose(buy.commission, 3.0)
    assert np.isclose(buy.stamp_duty, 0.0)
    assert np.isclose(buy.slippage_cost, 5.0)
    assert np.isclose(buy.total_cost, 8.0)
    assert np.isclose(buy.execution_price, 10.005)
    # --------------------------------------------------------
    # Sell
    # --------------------------------------------------------
    sell = engine.calculate_trade(
        price=10.0,
        quantity=1000,
        side=TradeSideV392.SELL,
    )
    assert np.isclose(sell.commission, 3.0)
    assert np.isclose(sell.stamp_duty, 5.0)
    assert np.isclose(sell.slippage_cost, 5.0)
    assert np.isclose(sell.total_cost, 13.0)
    assert np.isclose(sell.execution_price, 9.995)
    # --------------------------------------------------------
    # Vectorized
    # --------------------------------------------------------
    trades = pd.DataFrame(
        {
            "date": [
                "2026-01-01",
                "2026-01-02",
            ],
            "code": [
                "000001",
                "000001",
            ],
            "price": [
                10.0,
                10.5,
            ],
            "quantity": [
                1000,
                1000,
            ],
            "side": [
                "buy",
                "sell",
            ],
        }
    )
    result = calculate_transaction_costs_v392(
        trades,
        config=config,
    )
    assert len(result) == 2
    assert np.isclose(
        result["total_cost"].iloc[0],
        8.0,
    )
    assert np.isclose(
        result["total_cost"].iloc[1],
        13.65,
    )
    summary = summarize_costs_v392(result)
    assert (
        summary.number_of_trades == 2
    )
    assert (
        summary.total_cost > 0
    )
    # --------------------------------------------------------
    # Turnover
    # --------------------------------------------------------
    turnover = pd.Series(
        [0.1, 0.2, 0.3]
    )
    turnover_result = (
        calculate_turnover_cost_v392(
            turnover,
            config=config,
        )
    )
    assert (
        "total_cost" in turnover_result.columns
    )
    # --------------------------------------------------------
    # Net return
    # --------------------------------------------------------
    gross = pd.Series(
        [0.01, 0.02, -0.01]
    )
    cost = pd.Series(
        [0.001, 0.001, 0.001]
    )
    net = apply_transaction_cost_v392(
        gross,
        cost,
    )
    assert np.isclose(
        net.iloc[0],
        0.009,
    )
    print("backtest/costs.py V392 self-test passed.")


if __name__ == "__main__":
    _self_test_v392()
