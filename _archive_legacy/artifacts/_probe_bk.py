import requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Referer": "https://quote.eastmoney.com/"}
p = {"ut":"7eea3edcaed734bea9cbfc24409ed989","dpt":"wz.ztzt","Pageindex":"0","pagesize":"5","sort":"f62:desc","date":"20261120"}
for u in ["https://push2ex.eastmoney.com/getTopicBKList", "https://push2ex.eastmoney.com/getTopicPlateList"]:
    try:
        r=requests.get(u,params=p,headers=H,timeout=15); print(u,r.status_code,r.text[:400])
    except Exception as e: print(u,"ERR",repr(e))
