import json, time
import requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

def show(name, url, params, ref):
    try:
        r = requests.get(url, params=params, headers={**H, "Referer": ref}, timeout=20)
        print(name, r.status_code, r.text[:260].replace("\n", " "))
    except Exception as e:
        print(name, "ERR", repr(e))

show("em_quote", "https://push2.eastmoney.com/api/qt/stock/get", {"secid":"1.600519","fltt":"2","fields":"f43,f57,f58,f116,f117,f162,f167,f168,f169,f170,f127,f128,f129"}, "https://quote.eastmoney.com/")
time.sleep(2)
show("em_zt", "https://push2ex.eastmoney.com/getTopicZTPool", {"ut":"7eea3edcaed734bea9cbfc24409ed989","dpt":"wz.ztzt","Pageindex":"0","pagesize":"10","sort":"fbt:asc","date":"20261120"}, "https://quote.eastmoney.com/")
time.sleep(2)
show("em_flow", "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get", {"lmt":"0","klt":"101","secid":"1.600519","ut":"b288e3eb9b7d4b6eb9d2f8d9b1c7ff9c","fields1":"f1,f2,f3,f7","fields2":"f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"}, "https://quote.eastmoney.com/")
time.sleep(2)
show("em_lhb", "https://datacenter-web.eastmoney.com/api/data/v1/get", {"reportName":"RPT_DAILYBILLBOARD_DETAILSNEW","columns":"ALL","filter":"(TRADE_DATE='2026-11-20')","pageNumber":"1","pageSize":"3","sortColumns":"BILLBOARD_NET_AMT","sortTypes":"-1","source":"WEB","client":"WEB"}, "https://data.eastmoney.com/")
time.sleep(2)
show("sina", "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData", {"page":"1","num":"100","sort":"changepercent","asc":"0","node":"hs_a","symbol":"","_s_r_a":"page"}, "https://vip.stock.finance.sina.com.cn/")
