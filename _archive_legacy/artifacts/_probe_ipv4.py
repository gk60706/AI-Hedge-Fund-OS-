import socket, time, requests
orig=socket.getaddrinfo
def gai(host, port, family=0, type=0, proto=0, flags=0):
    return orig(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo=gai
for u in ["https://qt.gtimg.cn/q=sh600519","https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=100&sort=changepercent&asc=0&node=hs_a&symbol=&_s_r_a=page","https://push2delay.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f2,f3,f12,f14"]:
 t=time.time()
 try:
  r=requests.get(u,headers={"User-Agent":"Mozilla/5.0"},timeout=15)
  print(u.split("?")[0],r.status_code,len(r.content),round(time.time()-t,2))
 except Exception as e: print("ERR",type(e).__name__,str(e)[:100],round(time.time()-t,2))
