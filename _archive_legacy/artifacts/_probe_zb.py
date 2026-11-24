import requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Referer": "https://quote.eastmoney.com/"}
p = {"ut":"7eea3edcaed734bea9cbfc24409ed989","dpt":"wz.ztzt","Pageindex":"0","pagesize":"5","sort":"fbt:asc","date":"20261120"}
for n,u in [("zb","https://push2ex.eastmoney.com/getTopicZBPool"),("zb2","https://push2ex.eastmoney.com/getTopicZBPool")]:
    try:
        r=requests.get(u,params=p,headers=H,timeout=15); print(n,r.status_code,r.text[:300])
    except Exception as e: print(n,"ERR",repr(e))
