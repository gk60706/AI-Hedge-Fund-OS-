import time, requests
H={"User-Agent":"Mozilla/5.0","Referer":"https://vip.stock.finance.sina.com.cn/"}
for repeat in range(2):
    t=time.time(); counts=[]
    for page in range(1,6):
        r=requests.get("https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData",params={"page":page,"num":100,"sort":"changepercent","asc":0,"node":"hs_a","symbol":"","_s_r_a":"page"},headers=H,timeout=15)
        counts.append(len(r.json()) if r.status_code==200 else -r.status_code)
    print("seq", repeat, counts, round(time.time()-t,2))
