"""V2.4 盘中自主交易系统主流程（模拟盘演示）。"""

from portfolio.account import Account
from execution.simulator import SimulatorBroker
from execution.order import Order
from strategy.signal_engine import SignalEngine

account = Account(1000000)
broker = SimulatorBroker(account)
signal = SignalEngine()

analysis = {"capital": 90, "risk": "LOW"}
decision = signal.generate(analysis)

if decision == "BUY":
    order = Order(code="300394", side="BUY", price=120, quantity=100)
    result = broker.send_order(order)
    print(result)
    print(account.positions)
