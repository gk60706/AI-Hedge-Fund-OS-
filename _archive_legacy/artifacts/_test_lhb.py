from market_app import market_context as mc
r=mc.dragon_tiger(limit=8)
print(r["ok"], r["date"], r["count"], r["items"][:2])
p=mc.stock_profile("688279.SH")
print(p["market_cap_yi"], p["float_cap_yi"], p["pe_ttm"], p["pb"])
