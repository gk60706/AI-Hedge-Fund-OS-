import json
import requests
H = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
params = {"pn":"1","pz":"5","po":"1","np":"1","fltt":"2","invt":"2","fid":"f62","fs":"m:90+t:2","fields":"f12,f14,f2,f3,f62,f184,f204,f205,f124"}
hosts = [
 "https://push2.eastmoney.com/api/qt/clist/get",
 "https://push2delay.eastmoney.com/api/qt/clist/get",
 "https://push2his.eastmoney.com/api/qt/clist/get",
 "https://82.push2.eastmoney.com/api/qt/clist/get",
 "https://1.push2.eastmoney.com/api/qt/clist/get",
]
for url in hosts:
    try:
        r = requests.get(url, params=params, headers=H, timeout=15)
        print(url, r.status_code, r.text[:300])
    except Exception as e:
        print(url, "ERR", repr(e))
