"""AkShare 历史日线 API 兼容层。"""

import akshare as ak

_ak_hist_cache = None


def _resolve_ak_hist():
    for name in ("stock_zh_a_hist_em", "stock_zh_a_hist"):
        func = getattr(ak, name, None)
        if callable(func):
            return func

    raise RuntimeError(
        "当前 AkShare 版本不支持历史日线接口："
        "stock_zh_a_hist_em / stock_zh_a_hist"
    )


def _ak_hist(*args, **kwargs):
    global _ak_hist_cache

    if _ak_hist_cache is None:
        _ak_hist_cache = _resolve_ak_hist()

    return _ak_hist_cache(*args, **kwargs)
