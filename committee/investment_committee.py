"""V1.3 CIO 投资委员会：召集全部投资经理开会并表决。"""

from committee.voting import VotingSystem


class InvestmentCommittee:
    """投资委员会。

    对同一标的召集全部投资经理发表观点，再由投票系统表决。
    """

    def __init__(self, managers: list) -> None:
        self.managers = managers
        self.vote_system = VotingSystem()

    def meeting(self, stock: dict) -> dict:
        opinions = []
        for manager in self.managers:
            result = manager.analyze(stock)
            opinions.append(result)
        decision = self.vote_system.vote(opinions)
        return {
            "opinions": opinions,
            "decision": decision,
        }
