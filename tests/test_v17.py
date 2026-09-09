"""V1.7 强化学习交易 Agent 测试"""
import numpy as np
import pytest

from rl.action import Action
from rl.environment import TradingEnvironment
from rl.reward import RewardEngine
from rl.state import MarketState
from rl.trainer import RLTrainer

from risk.position_sizer import PositionSizer
from risk.risk_gate import RiskGate

from evaluation.rl_evaluator import RLEvaluator

torch = pytest.importorskip("torch")
from rl.dqn_agent import DQNAgent  # noqa: E402
from rl.ppo_agent import ActorCritic  # noqa: E402


class TestMarketState:
    def test_vector(self):
        s = MarketState(
            price=10.0, return_1d=0.01, return_5d=0.05,
            volatility=0.02, volume_ratio=1.2, momentum=0.03,
            position=0.5, cash_ratio=0.5,
        )
        v = s.to_vector()
        assert len(v) == 7
        assert v[0] == 0.01


class TestAction:
    def test_values(self):
        assert Action.SELL == 0
        assert Action.HOLD == 1
        assert Action.BUY == 2


class TestTradingEnvironment:
    def test_step(self):
        prices = np.linspace(100, 110, 50)
        features = np.zeros((50, 5))
        env = TradingEnvironment(prices=prices, features=features)
        state = env.reset()
        assert state.shape == (7,)
        ns, reward, done, info = env.step(Action.BUY)
        assert not done
        assert "portfolio_value" in info
        # BUY 后全仓持仓
        assert env.position > 0

    def test_done(self):
        prices = np.linspace(100, 110, 5)
        features = np.zeros((5, 5))
        env = TradingEnvironment(prices=prices, features=features)
        env.reset()
        for _ in range(3):
            env.step(Action.HOLD)
        _, _, done, _ = env.step(Action.HOLD)
        assert done


class TestRewardEngine:
    def test_positive(self):
        r = RewardEngine().calculate(0.05, 0.0, 1)
        assert r == pytest.approx(0.04)

    def test_drawdown_penalty(self):
        r = RewardEngine().calculate(0.05, 0.10, 1)
        assert r < 0.05


class TestRiskGate:
    def test_daily_loss(self):
        out = RiskGate().check(2, 1_000_000, 0.05, -0.04)
        assert out["approved"] is False
        assert out["reason"] == "DAILY_LOSS_LIMIT"

    def test_drawdown(self):
        out = RiskGate().check(2, 1_000_000, 0.12, 0.0)
        assert out["approved"] is False

    def test_normal(self):
        out = RiskGate().check(2, 1_000_000, 0.05, 0.01)
        assert out["approved"] is True


class TestPositionSizer:
    def test_calc(self):
        assert PositionSizer().calculate(0.90) == 0.18

    def test_clamp(self):
        assert PositionSizer().calculate(1.5) == 0.20
        assert PositionSizer().calculate(-0.5) == 0.0


class TestRLEvaluator:
    def test_evaluate(self):
        out = RLEvaluator().evaluate([100, 110, 121])
        assert out["total_return"] == pytest.approx(0.21)
        assert out["max_drawdown"] == 0.0
        assert out["sharpe"] >= 0


class TestDQN:
    def test_act(self):
        agent = DQNAgent(state_size=7, action_size=3)
        a = agent.act(np.zeros(7, dtype=np.float32))
        assert a in (0, 1, 2)

    def test_decay(self):
        agent = DQNAgent(state_size=7, action_size=3)
        e0 = agent.epsilon
        agent.decay_epsilon()
        assert agent.epsilon < e0


class TestActorCritic:
    def test_forward(self):
        net = ActorCritic(state_size=7, action_size=3)
        logits, value = net(torch.randn(7))
        assert logits.shape == (3,)
        assert value.shape == (1,)


class TestRLTrainer:
    def test_train(self):
        prices = np.linspace(100, 108, 40)
        features = np.zeros((40, 5))
        env = TradingEnvironment(prices=prices, features=features)
        agent = DQNAgent(state_size=7, action_size=3)
        history = RLTrainer().train(env, agent, episodes=2)
        assert len(history) == 2
        assert history[0]["portfolio"] > 0
