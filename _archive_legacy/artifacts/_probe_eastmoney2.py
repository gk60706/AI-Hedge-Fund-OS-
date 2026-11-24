import json

import requests

H = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
tests = {
    "fflow_daykline_push2": (
        "https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get",
        {
            "lmt": "0",
            "klt": "101",
            "secid": "1.600519",
            "ut": "b288e3eb9b7d4b6eb9d2f8d9b1c7ff9c",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        },
    ),
    "fflow_daykline_his": (
        "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
        {
            "lmt": "0",
            "klt": "101",
            "secid": "1.600519",
            "ut": "b288e3eb9b7d4b6eb9d2f8d9b1c7ff9c",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
        },
    ),
    "zt_pool_1120": (
        "https://push2ex.eastmoney.com/getTopicZTPool",
        {
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "dpt": "wz.ztzt",
            "Pageindex": "0",
            "pagesize": "20",
            "sort": "fbt:asc",
            "date": "20261120",
        },
    ),
    "all_a_5000": (
        "https://push2.eastmoney.com/api/qt/clist/get",
        {
            "pn": "1",
            "pz": "5000",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f2,f3,f5,f6,f8,f9,f10,f12,f13,f14,f20,f21,f23,f62,f100,f184",
        },
    ),
    "dragon_tiger": (
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        {
            "reportName": "RPT_DAILYBILLBOARD_DETAILSNEW",
            "columns": "ALL",
            "filter": "(TRADE_DATE='2026-11-20')",
            "pageNumber": "1",
            "pageSize": "5",
            "sortColumns": "BILLBOARD_NET_AMT",
            "sortTypes": "-1",
            "source": "WEB",
            "client": "WEB",
        },
    ),
}
for name, (url, params) in tests.items():
    try:
        r = requests.get(url, params=params, headers=H, timeout=20)
        print("==", name, r.status_code, r.url[:150])
        try:
            j = r.json()
            txt = json.dumps(j, ensure_ascii=False)
            print(txt[:1200])
            data = j.get("data")
            if isinstance(data, dict) and isinstance(data.get("diff"), list):
                print("count=", len(data["diff"]), "total=", data.get("total"))
        except Exception:
            print(r.text[:500])
    except Exception as e:
        print("==", name, "ERR", repr(e))
