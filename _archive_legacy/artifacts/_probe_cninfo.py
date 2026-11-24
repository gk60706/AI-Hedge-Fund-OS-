import requests, time, json
t=time.time()
r=requests.get("http://www.cninfo.com.cn/new/data/szse_stock.json",headers={"User-Agent":"Mozilla/5.0"},timeout=30)
print("status",r.status_code,"len",len(r.content),"t",round(time.time()-t,1))
try:
 j=r.json(); arr=j.get("stockList") or j
 print("type",type(j).__name__,"keys",list(j)[:5] if isinstance(j,dict) else None,"n",len(arr))
 print(json.dumps(arr[:2],ensure_ascii=False))
 from collections import Counter
 print(Counter(str(x.get("code"))[:3] for x in arr).most_common(12))
 print(Counter(x.get("category") for x in arr).most_common(8))
except Exception as e: print("JSONERR",type(e).__name__,str(e)[:200],r.text[:200])
