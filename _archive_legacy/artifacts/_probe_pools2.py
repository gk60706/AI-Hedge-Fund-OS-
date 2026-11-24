import requests, json
from urllib3.util import connection
connection.HAS_IPV6=False
p={"ut":"7eea3edcaed734bea9cbfc24409ed989","dpt":"wz.ztzt","Pageindex":"0","pagesize":"100","sort":"fbt:asc","date":"20261123"}
for kind in ["getTopicDTPool","getTopicZTPool","getTopicZBPool"]:
 r=requests.get(f"https://push2ex.eastmoney.com/{kind}",params=p,headers={"User-Agent":"Mozilla/5.0","Referer":"https://quote.eastmoney.com/"},timeout=15)
 j=r.json(); d=j.get("data") or {}
 print(kind,"rc",j.get("rc"),"tc",d.get("tc"),"keys",list(d)[:10],"pool_n",len(d.get("pool") or []))
 if d.get("pool"): print(json.dumps(d["pool"][0],ensure_ascii=False)[:500])
