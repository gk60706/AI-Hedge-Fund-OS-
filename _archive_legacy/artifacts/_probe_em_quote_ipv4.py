import socket, time, requests
from urllib3.util import connection
connection.HAS_IPV6=False
H={"User-Agent":"Mozilla/5.0","Referer":"https://quote.eastmoney.com/"}
for host in ["push2.eastmoney.com","push2delay.eastmoney.com"]:
 u=f"https://{host}/api/qt/stock/get"
 p={"secid":"1.600519","ut":"fa5fd1943c7b386f172d6893dbfba10b","invt":"2","fltt":"2","fields":"f43,f57,f58,f116,f117,f162,f167,f168,f169,f170,f127,f128,f129,f100,f102,f103"}
 t=time.time()
 try:
  r=requests.get(u,params=p,headers=H,timeout=15); j=r.json()
  print(host,r.status_code,round(time.time()-t,2),j.get("rc"),str(j.get("data"))[:300])
 except Exception as e: print(host,"ERR",type(e).__name__,str(e)[:100],round(time.time()-t,2))
