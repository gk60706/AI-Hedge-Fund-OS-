"""订单系统 (V0.7)

模拟交易订单：code/action/price/volume/time。
"""
from datetime import datetime


class Order:
    """模拟交易订单。"""

    def __init__(self, code: str, action: str, price: float, volume: int):
        self.code = code
        self.action = action
        self.price = price
        self.volume = volume
        self.time = datetime.now()

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "action": self.action,
            "price": self.price,
            "volume": self.volume,
            "time": str(self.time),
        }

# ============================================================
# V3.0 AI Autonomous Hedge Fund：模拟交易 Order
# ============================================================
from dataclasses import dataclass
from enum import Enum


class OrderSideV30(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class OrderV30:
    code: str
    side: OrderSideV30
    quantity: int
    price: float
    order_id: str = ""
    status: str = "PENDING"
