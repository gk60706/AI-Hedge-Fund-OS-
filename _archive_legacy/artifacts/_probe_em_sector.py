import json
import requests
H = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
url2 = "https://push2.eastmoney.com/api/qt/clist/get"
for po in ("1", "0"):
    p2 = {"pn":"1","pz":"8","po":po,"np":"1","fltt":"2","invt":"2","fid":"f62","fs":"m:90+t:2","fields":"f12,f14,f2,f3,f62,f184,f204,f205,f124"}
    try:
        r2 = requests.get(url2, params=p2, headers=H, timeout=20)
        print("po", po, r2.status_code)
        j = r2.json()
        print(json.dumps(j, ensure_ascii=False)[:700])
    except Exception as e:
        print("po", po, "ERR", repr(e))
