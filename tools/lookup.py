import json, time, requests
H = {"User-Agent": "Mozilla/5.0"}
def get(url):
    for i in range(3):
        try:
            r = requests.get(url, timeout=30, headers=H); r.raise_for_status(); return r.json()
        except Exception as e:
            err = e; time.sleep(2)
    return {"error": str(err)}
cands = {}
for q in ["Nifty 500 Index", "Nifty Midcap 150 Index", "LargeMidcap 250", "Large Midcap 250", "Nifty 50 Index Fund Direct"]:
    print(f"\n=== search: {q}")
    res = get("https://api.mfapi.in/mf/search?q=" + requests.utils.quote(q))
    if isinstance(res, dict): print(res); continue
    for s in res:
        n = s["schemeName"]; u = n.upper()
        if any(x in u for x in ("IDCW", "DIVIDEND", "BONUS", "ETF", "MOMENTUM", "VALUE", "QUALITY", "LOW VOL", "ALPHA", "EQUAL")): continue
        if "DIRECT" not in u: continue
        print(s["schemeCode"], "|", n); cands[s["schemeCode"]] = n
print("\n=== history span of candidates (+120323 name check)")
for c in list(cands)[:40] + [120323, 120716]:
    d = get(f"https://api.mfapi.in/mf/{c}")
    if "data" not in d or not d["data"]: print(c, "| no data", str(d)[:100]); continue
    print(c, "|", d["meta"]["scheme_name"], "| first", d["data"][-1]["date"], "| last", d["data"][0]["date"], d["data"][0]["nav"], "| rows", len(d["data"]))
