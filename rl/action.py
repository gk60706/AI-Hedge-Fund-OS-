"""V1.7 交易动作定义（研究/模拟）。"""

from enum import IntEnum


class Action(IntEnum):
    SELL = 0
    HOLD = 1
    BUY = 2
