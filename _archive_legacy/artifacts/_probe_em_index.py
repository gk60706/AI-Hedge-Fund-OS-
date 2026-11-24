import json
import requests

H = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
params = {
    "secid": "1.000001", "klt": "101", "fqt": "1", "lmt": "3",
    "fields1": "f1,f2,f3,f4,f5,f6",
    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
}
r = requests.get(url, params=params, headers=H, timeout=20)
print(r.status_code)
j = r.json()
print(json.dumps(j, ensure_ascii=False)[:1200])

# sector flow bottom
url2 = "https://push2.eastmoney.com/api/qt/clist/get"
p2 = {"pn":"1","pz":"5","po":"0","np":"1","fltt":"2","invt":"2","fid":"f62","fs":"m:90+t:2","fields":"f12,f14,f2,f3,f62,f184,f204,f205,f124"}
r2 = requests.get(url2, params=p2, headers=H, timeout=20)
print(r2.status_code, r2.text[:500])
