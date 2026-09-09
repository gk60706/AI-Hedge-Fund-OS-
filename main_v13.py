"""V1.3 完整运行入口：AI 基金团队 → 投委会投票 → 竞技场竞争 → 排名 → 冠军上线 → 资金分配。

研究/模拟用途，不含任何自动实盘交易接口。
"""

from allocation.capital_allocator import CapitalAllocator
from arena.battle import StrategyArena
from arena.champion import ChampionStrategy
from arena.ranking import StrategyRanking
from committee.investment_committee import InvestmentCommittee
from fund.team import create_team


def main() -> None:
    # 创建 AI 基金团队
    team = create_team()

    # 股票池测试
    stock = {
        "code": "300394",
        "pe": 25,
        "roe": 22,
        "momentum": 1,
        "volume": 2,
        "alpha": 90,
    }

    # 投资委员会
    committee = InvestmentCommittee(team)
    meeting = committee.meeting(stock)
    print("投委会结果:")
    print(meeting)

    # 策略竞技
    arena = StrategyArena(team)
    results = arena.compete(stock)
    print("策略竞争:")
    print(results)

    # 排名
    ranking = StrategyRanking().rank(results)
    print("策略排名:")
    print(ranking)

    # 冠军策略
    champion = ChampionStrategy().deploy(ranking)
    print("上线策略:")
    print(champion)

    # 资金分配
    allocator = CapitalAllocator()
    portfolio = allocator.allocate(ranking, 10000000)
    print("资金配置:")
    print(portfolio)


if __name__ == "__main__":
    main()
