"""V2.4 模拟券商接口：统一接口，未来接 QMT / 真实券商 API。"""


class Broker:
    """券商接口抽象基类。"""

    def send_order(self, order):
        raise NotImplementedError
