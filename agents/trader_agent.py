"""AI 交易 Agent (V0.7)

根据决策分数生成模拟交易信号（BUY/SELL/HOLD）。
"""


def trader_agent(decision: dict) -> dict:
    """AI 交易 Agent。

    :param decision: 含 ``code``/``score``/``price`` 的决策
    :return: 交易信号 ``{"code", "action", "price", "volume": 1000}``
    """
    score = decision["score"]
    if score >= 80:
        action = "BUY"
    elif score <= 40:
        action = "SELL"
    else:
        action = "HOLD"
    return {
        "code": decision["code"],
        "action": action,
        "price": decision["price"],
        "volume": 1000,
    }


# ---------------------------------------------------------------------------
# V2.0 交易 Agent（多智能体基金经理系统）：把决策转为模拟交易指令。
# 与 V0.7 trader_agent 函数并存，不删除已有功能。
# ---------------------------------------------------------------------------
class TraderAgent:
    """V2.0 交易执行 Agent（仅生成模拟指令，无实盘接口）。"""

    def execute(self, decision: str) -> dict:
        """Args:
            decision: BUY / SELL / 其他。

        Returns:
            模拟指令（OPEN_POSITION / CLOSE_POSITION / WAIT）。
        """
        if decision == "BUY":
            return {"action": "OPEN_POSITION", "position": 0.2}
        if decision == "SELL":
            return {"action": "CLOSE_POSITION"}
        return {"action": "WAIT"}
