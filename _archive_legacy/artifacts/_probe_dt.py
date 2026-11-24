import requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Referer": "https://quote.eastmoney.com/"}
base = {"ut":"7eea3edcaed734bea9cbfc24409ed989","dpt":"wz.ztzt","Pageindex":"0","pagesize":"3","sort":"fund:asc","date":"20261120"}
for name, url in [
 ("dt1", "https://push2ex.eastmoney.com/getTopicDTPool"),
 ("dt2", "https://push2ex.eastmoney.com/getTopicDTPool"),
]:
    try:
        r = requests.get(url, params=base, headers=H, timeout=15)
        print(name, r.status_code, r.text[:400])
    except Exception as e:
        print(name, "ERR", repr(e))
