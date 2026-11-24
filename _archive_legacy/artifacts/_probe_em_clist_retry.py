import requests, time
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36","Referer":"https://quote.eastmoney.com/"}
params={"pn":"1","pz":"6000","po":"1","np":"1","ut":"bd1d9ddb04089700cf9c27f6f7426281","fltt":"2","invt":"2","fid":"f3","fs":"m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23","fields":"f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152"}
for host in ["push2.eastmoney.com","push2delay.eastmoney.com","82.push2.eastmoney.com","push2his.eastmoney.com"]:
    t=time.time()
    try:
        r=requests.get(f"https://{host}/api/qt/clist/get",params=params,headers=H,timeout=25)
        j=r.json()
        d=j.get("data")
        print(host,r.status_code,"total",(d or {}).get("total"),"n",len((d or {}).get("diff") or []),round(time.time()-t,1))
        if d and d.get("diff"): print(list(d["diff"][0].items())[:6])
    except Exception as e:
        print(host,"ERR",type(e).__name__,str(e)[:120],round(time.time()-t,1))
