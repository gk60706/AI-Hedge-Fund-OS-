import requests, json
H={"User-Agent":"Mozilla/5.0","Referer":"https://vip.stock.finance.sina.com.cn/"}
base={"page":"1","num":"100","sort":"changepercent","asc":"0","node":"hs_a","_s_r_a":"page"}
for sym in ["sh600519","sz300750","bj920067"]:
    p={**base,"symbol":sym}
    try:
        r=requests.get("https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData",params=p,headers=H,timeout=15)
        print(sym,r.status_code,r.text[:300])
    except Exception as e: print(sym,"ERR",repr(e))
