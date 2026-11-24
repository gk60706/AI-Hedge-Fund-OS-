import json

import requests

H = {"User-Agent": "Mozilla/5.0", "Referer": "https://vip.stock.finance.sina.com.cn/"}
url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
for num in (80, 500, 1000):
    try:
        r = requests.get(url, params={"page": "1", "num": str(num), "sort": "changepercent", "asc": "0", "node": "hs_a", "symbol": "", "_s_r_a": "page"}, headers=H, timeout=25)
        print("num", num, r.status_code, len(r.text), r.text[:300])
        try:
            data = json.loads(r.text)
            print("parsed", len(data), data[0] if data else None)
        except Exception as e:
            print("json err", e)
    except Exception as e:
        print("num", num, "ERR", repr(e))
