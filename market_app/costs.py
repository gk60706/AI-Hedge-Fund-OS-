from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CostModel:
    """A-share cash-equity transaction cost model for backtests.

    The model deliberately uses a fixed notional per trade instead of a
    compounding portfolio.  That keeps signal-quality comparison clean while
    still applying minimum commission, stamp duty and slippage correctly.

    Defaults are configurable through the backtest CLI; they are research
    assumptions, not exchange-published constants.
    """

    commission_rate: float = 0.00025  # 万 2.5，双边
    min_commission: float = 5.0       # 单笔最低 5 元
    stamp_duty_rate: float = 0.0005   # 印花税，仅卖出
    transfer_fee_rate: float = 0.00001  # 过户费 0.001%，双边
    slippage_rate: float = 0.001      # 单边滑点 0.1%
    capital: float = 100000.0         # 每笔固定名义本金

    def buy_fill_price(self, raw_open: float) -> float:
        return float(raw_open) * (1.0 + float(self.slippage_rate))

    def sell_fill_price(self, raw_close: float) -> float:
        return float(raw_close) * (1.0 - float(self.slippage_rate))

    def buy_fees(self, gross: float) -> dict[str, float]:
        commission = max(float(gross) * self.commission_rate, self.min_commission)
        transfer = float(gross) * self.transfer_fee_rate
        return {
            "commission": round(commission, 4),
            "transfer": round(transfer, 4),
            "stamp": 0.0,
            "total": round(commission + transfer, 4),
        }

    def sell_fees(self, gross: float) -> dict[str, float]:
        commission = max(float(gross) * self.commission_rate, self.min_commission)
        stamp = float(gross) * self.stamp_duty_rate
        transfer = float(gross) * self.transfer_fee_rate
        return {
            "commission": round(commission, 4),
            "transfer": round(transfer, 4),
            "stamp": round(stamp, 4),
            "total": round(commission + stamp + transfer, 4),
        }

    def trade_return(self, entry_raw: float, exit_raw: float) -> dict[str, float]:
        """Return gross/net percentage and total fees for one round trip.

        ``gross_return_pct`` uses raw open/close, excluding all friction.
        ``net_return_pct`` uses slipped fill prices and all fees, with a fixed
        ``capital`` notional per trade.
        """

        entry_raw = float(entry_raw)
        exit_raw = float(exit_raw)
        if entry_raw <= 0 or exit_raw <= 0:
            raise ValueError("entry/exit price must be positive")

        buy_price = self.buy_fill_price(entry_raw)
        sell_price = self.sell_fill_price(exit_raw)
        shares = float(self.capital) / buy_price
        buy_gross = shares * buy_price
        buy_fee_detail = self.buy_fees(buy_gross)
        buy_total = buy_gross + buy_fee_detail["total"]

        sell_gross = shares * sell_price
        sell_fee_detail = self.sell_fees(sell_gross)
        sell_net = sell_gross - sell_fee_detail["total"]

        gross_return_pct = (exit_raw / entry_raw - 1.0) * 100.0
        net_return_pct = (sell_net / buy_total - 1.0) * 100.0
        total_fees = buy_fee_detail["total"] + sell_fee_detail["total"]

        return {
            "entry_fill": round(buy_price, 4),
            "exit_fill": round(sell_price, 4),
            "shares": round(shares, 4),
            "buy_fees": round(buy_fee_detail["total"], 4),
            "sell_fees": round(sell_fee_detail["total"], 4),
            "total_fees": round(total_fees, 4),
            "gross_return_pct": round(gross_return_pct, 4),
            "net_return_pct": round(net_return_pct, 4),
            "cost_drag_pct": round(gross_return_pct - net_return_pct, 4),
            "buy_commission": buy_fee_detail["commission"],
            "buy_transfer": buy_fee_detail["transfer"],
            "sell_commission": sell_fee_detail["commission"],
            "sell_transfer": sell_fee_detail["transfer"],
            "sell_stamp": sell_fee_detail["stamp"],
        }

    def as_dict(self) -> dict[str, float]:
        return asdict(self)
