import requests, time
from urllib3.util import connection
connection.HAS_IPV6=False
p={"pn":"1","pz":"8","po":"1","np":"1","fltt":"2","invt":"2","fid":"f62","fs":"m:90+t:2","fields":"f12,f14,f2,f3,f62,f184,f204,f205,f124","ut":"bd1d9ddb04089700cf9c27f6f7426281"}
for h in ["push2delay.eastmoney.com","push2.eastmoney.com"]:
 t=time.time()
 try:
  r=requests.get(f"https://{h}/api/qt/clist/get",params=p,headers={"User-Agent":"Mozilla/5.0","Referer":"https://quote.eastmoney.com/"},timeout=15)
  j=r.json(); d=j.get("data") or {}
  print(h,r.status_code,"total",d.get("total"),"n",len(d.get("diff") or []),"t",round(time.time()-t,2))
  print((d.get("diff") or [{}])[0])
 except Exception as e: print(h,"ERR",type(e).__name__,str(e)[:100],round(time.time()-t,2))
