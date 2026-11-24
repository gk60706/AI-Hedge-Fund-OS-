import requests, time
H={"User-Agent":"Mozilla/5.0","Referer":"https://gu.qq.com/"}
urls=[
 "https://proxy.finance.qq.com/cgi/cgi-bin/rank/pt/getRank?board=hs&sort=price&page=1&num=100",
 "https://proxy.finance.qq.com/cgi/cgi-bin/rank/pt/getRank?board=hs&sort=zdf&page=1&num=100",
 "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/rank/rank?board=hs&sort=price&page=1&num=100",
 "https://stock.gtimg.cn/data/index.php?appn=rank&t=rankash/chr&p=1&o=0&l=40&v=list_data",
]
for u in urls:
 t=time.time()
 try:
  r=requests.get(u,headers=H,timeout=15)
  print("URL",u.split('?')[0],"status",r.status_code,"len",len(r.text),"t",round(time.time()-t,1),"head",r.text[:180].replace("\n"," "))
 except Exception as e: print("URL",u.split('?')[0],"ERR",type(e).__name__,str(e)[:100],"t",round(time.time()-t,1))
