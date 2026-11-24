import json, time
from market_app import market_context as mc

t0 = time.time()
snap = mc.market_snapshot()
print("snapshot", snap["count"], snap["coverage"], round(time.time()-t0,1))

latest = mc.latest_trade_date()
print("latest", latest)

sent = mc.market_sentiment()
print("sentiment", sent["as_of"], sent["breadth"])
print("zt", sent["limit_up"]["count"], "dt", sent["limit_down"]["count"], "zb", sent["broken_board"]["count"], "seal", sent["limit_up"]["seal_rate"])
print("sector", sent["sectors"].get("ok"), sent["sectors"].get("error"))
print("lhb", sent["dragon_tiger"].get("ok"), sent["dragon_tiger"].get("count"), sent["dragon_tiger"].get("error"))
print("first_zt", json.dumps((sent["limit_up"]["items"] or [None])[0], ensure_ascii=False))

radar = mc.radar_query(min_pct=2, max_pct=8, min_turnover=2, max_cap_yi=2000, sort="pct", limit=10)
print("radar", radar["total"], radar["matched"], radar["displayed"])
print("radar_first", json.dumps((radar["items"] or [None])[0], ensure_ascii=False))

profile = mc.stock_profile("600519.SH")
print("profile", json.dumps(profile, ensure_ascii=False)[:600])
flow = mc.stock_flow("600519.SH", days=10)
print("flow", flow["ok"], flow.get("summary"), (flow.get("items") or [None])[-1])
print("elapsed", round(time.time()-t0,1))
