"""V2.4 交易订单系统。"""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Order:
    """交易订单。"""

    code: str
    side: str  # BUY / SELL
    price: float
    quantity: int
    time: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
