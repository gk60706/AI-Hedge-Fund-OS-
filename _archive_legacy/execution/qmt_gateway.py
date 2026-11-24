"""V2.4 QMT 接口预留：未来连接 miniQMT / QMT Python API / 券商交易接口。"""


class QMTGateway:
    """QMT 交易网关（占位，禁止直接用于实盘）。"""

    def connect(self):
        print("QMT接口等待连接")

    def buy(self, code, amount):
        print("QMT BUY", code, amount)
