import requests, time, json
from concurrent.futures import ThreadPoolExecutor
from urllib3.util import connection
connection.HAS_IPV6=False
H={"User-Agent":"Mozilla/5.0","Referer":"https://gu.qq.com/"}
j=requests.get("http://www.cninfo.com.cn/new/data/szse_stock.json",headers=H,timeout=10).json()
arr=[x for x in j["stockList"] if x.get("category")=="A股"]
def sym(code):
    if code.startswith("6"): return "sh"+code
    if code.startswith(("0","3")): return "sz"+code
    if code.startswith(("920","8","4")): return "bj"+code
    return "sh"+code
codes=[sym(x["code"]) for x in arr]
print("total",len(codes))
def fetch(chunk):
    t=time.time()
    txt=requests.get("https://qt.gtimg.cn/q="+",".join(chunk),headers=H,timeout=15).content.decode("gbk","ignore")
    lines=[l for l in txt.split(";") if '="' in l and "~" in l]
    return len(lines),round(time.time()-t,2),txt[:80]
chunks=[codes[i:i+50] for i in range(0,300,50)]
t=time.time()
with ThreadPoolExecutor(max_workers=6) as ex:
    res=list(ex.map(fetch,chunks))
print("res",res,"wall",round(time.time()-t,2))
# find a bj code response
bj=[c for c in codes if c.startswith("bj")][:5]
print("bj",bj, fetch(bj)[:2])
txt=requests.get("https://qt.gtimg.cn/q="+",".join(bj),headers=H,timeout=15).content.decode("gbk","ignore")
print(txt[:300])
