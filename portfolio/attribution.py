"""V2.6 收益归因分析：回答「为什么赚钱」。"""


class Attribution:
    """收益来源归因。"""

    def analyze(self, returns):
        result = {}
        for item in returns:
            result[item] = returns[item]
        return result
