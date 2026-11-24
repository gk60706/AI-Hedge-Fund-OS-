import requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Referer": "https://quote.eastmoney.com/"}
p = {"secid":"1.600519","fltt":"2","fields":"f43,f57,f58,f116,f117,f162,f167,f168,f169,f170,f127,f128,f129"}
for host in ("push2delay.eastmoney.com", "push2his.eastmoney.com", "82.push2.eastmoney.com", "push2.eastmoney.com"):
    try:
        r = requests.get(f"https://{host}/api/qt/stock/get", params=p, headers=H, timeout=15)
        print(host, r.status_code, r.text[:240])
    except Exception as e:
        print(host, "ERR", repr(e))
