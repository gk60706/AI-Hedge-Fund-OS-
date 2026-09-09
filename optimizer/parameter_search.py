"""V1.2 参数自动优化：网格搜索策略参数组合，返回得分最高的配置。"""

import itertools


def optimize(params: dict, backtest) -> dict | None:
    """在参数网格上穷举搜索，返回回测得分最高的参数配置。

    :param params: ``{"param_name": [候选值, ...]}``
    :param backtest: 可调用对象，接收一个参数配置 dict，
                     返回含 ``score`` 键的 dict
    :return: 得分最高的参数配置 dict；参数为空时返回 None
    """
    keys = list(params.keys())
    if not keys:
        return None
    best = None
    best_score = -999
    for values in itertools.product(*params.values()):
        config = dict(zip(keys, values))
        result = backtest(config)
        if result["score"] > best_score:
            best_score = result["score"]
            best = config
    return best
