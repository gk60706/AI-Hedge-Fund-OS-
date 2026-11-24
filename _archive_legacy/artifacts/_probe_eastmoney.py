import json

import requests

H = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
tests = {
    "quote": (
        "https://push2.eastmoney.com/api/qt/stock/get",
        {
            "secid": "1.600519",
            "fltt": "2",
            "fields": "f43,f57,f58,f116,f117,f162,f167,f168,f169,f170,f127,f128,f129,f130,f131,f132,f133,f134,f135,f136,f137,f138,f139,f140,f141,f142,f143,f144,f145,f146,f147,f148,f149,f150,f151,f152",
        },
    ),
    "fflow_daily": (
        "https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get",
        {
            "lmt": "0",
            "klt": "101",
            "secid": "1.600519",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        },
    ),
    "sector_flow": (
        "https://push2.eastmoney.com/api/qt/clist/get",
        {
            "pn": "1",
            "pz": "10",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f62",
            "fs": "m:90+t:2",
            "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124",
        },
    ),
    "zt_pool": (
        "https://push2ex.eastmoney.com/getTopicZTPool",
        {
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "dpt": "wz.ztzt",
            "Pageindex": "0",
            "pagesize": "20",
            "sort": "fbt:asc",
            "date": "20261121",
        },
    ),
}
for name, (url, params) in tests.items():
    try:
        r = requests.get(url, params=params, headers=H, timeout=15)
        print("==", name, r.status_code, r.url[:140])
        try:
            j = r.json()
            print(json.dumps(j, ensure_ascii=False)[:900])
        except Exception:
            print(r.text[:500])
    except Exception as e:
        print("==", name, "ERR", repr(e))
