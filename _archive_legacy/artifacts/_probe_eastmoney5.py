import json

import requests

H = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
URL = "https://push2.eastmoney.com/api/qt/clist/get"
variants = {
    "a_no_bj": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
    "sh_only": "m:1+t:2",
    "sz_only": "m:0+t:6",
    "all_board": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
}
for name, fs in variants.items():
    for fid in ("f3", "f12"):
        try:
            params = {
                "po": "1", "np": "1", "fltt": "2", "invt": "2",
                "fid": fid, "fs": fs, "pn": "1", "pz": "20",
                "fields": "f2,f3,f5,f6,f8,f9,f10,f12,f13,f14,f20,f21,f23,f62,f100,f184",
            }
            r = requests.get(URL, params=params, headers=H, timeout=20)
            j = r.json()
            data = j.get("data") or {}
            diff = data.get("diff") or []
            print(name, fid, r.status_code, "total", data.get("total"), "rows", len(diff), "rc", j.get("rc"))
            if diff:
                print(json.dumps(diff[0], ensure_ascii=False)[:400])
                break
        except Exception as e:
            print(name, fid, "ERR", repr(e))
