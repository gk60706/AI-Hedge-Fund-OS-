import json

import requests

H = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
URL = "https://push2.eastmoney.com/api/qt/clist/get"
BASE = {
    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    "po": "1",
    "np": "1",
    "fltt": "2",
    "invt": "2",
    "fid": "f3",
    "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
    "fields": "f2,f3,f5,f6,f8,f9,f10,f12,f13,f14,f20,f21,f23,f62,f100,f184",
}
for pz in (100, 50, 20):
    try:
        r = requests.get(URL, params={**BASE, "pn": "1", "pz": str(pz)}, headers=H, timeout=20)
        j = r.json()
        data = j.get("data") or {}
        diff = data.get("diff") or []
        print("pz", pz, "status", r.status_code, "total", data.get("total"), "rows", len(diff))
        if diff:
            print(json.dumps(diff[0], ensure_ascii=False))
    except Exception as e:
        print("pz", pz, "ERR", repr(e))
