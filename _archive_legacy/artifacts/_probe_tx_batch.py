import requests, time, json
codes=["sh600519","sz000001","sz300750","sh601318","sz002594","sh688981"]
for n in [6,60,200]:
 q=",".join(codes*((n//len(codes))+1))[:0]
 if n==6: qs=codes
 elif n==60: qs=[f"sh{600000+i:06d}" for i in range(60)]
 else: qs=[f"sz{1+i:06d}" for i in range(200)]
 q=",".join(qs)
 t=time.time()
 try:
  r=requests.get("https://qt.gtimg.cn/q="+q,headers={"User-Agent":"Mozilla/5.0","Referer":"https://gu.qq.com/"},timeout=15)
  txt=r.content.decode("gbk","ignore")
  print("n",n,"status",r.status_code,"len",len(txt),"t",round(time.time()-t,2),"lines",txt.count(";"),"head",txt[:120].replace("\n"," "))
  first=txt.split(";")[0]
  print("fields",len(first.split("~")), first.split("~")[:10])
 except Exception as e: print("n",n,"ERR",type(e).__name__,str(e)[:100],"t",round(time.time()-t,2))
