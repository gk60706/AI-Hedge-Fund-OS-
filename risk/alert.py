"""实时风险预警系统 (V0.8)

检测持仓亏损跌破 -8% 并输出预警。
"""


def risk_alert(portfolio: list) -> list:
    """风险预警。

    :param portfolio: 持仓列表，元素含 ``code`` 与 ``loss``（收益率）
    :return: ``[{"code", "warning": "跌破止损"}]``
    """
    alerts = []
    for stock in portfolio:
        if stock["loss"] < -0.08:
            alerts.append({"code": stock["code"], "warning": "跌破止损"})
    return alerts
