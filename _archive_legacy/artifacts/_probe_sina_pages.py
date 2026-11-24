import json

import requests
from concurrent.futures import ThreadPoolExecutor

H = {"User-Agent": "Mozilla/5.0", "Referer": "https://vip.stock.finance.sina.com.cn/"}
url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"

def fetch(page):
    r = requests.get(url, params={"page": str(page), "num": "100", "sort": "changepercent", "asc": "0", "node": "hs_a", "symbol": "", "_s_r_a": "page"}, headers=H, timeout=20)
    data = r.json()
    return page, len(data), data[0]["code"] if data else None, data[-1]["code"] if data else None

with ThreadPoolExecutor(max_workers=5) as ex:
    for result in ex.map(fetch, [1, 2, 3, 10, 20, 30, 40, 50, 60]):
        print(result)
