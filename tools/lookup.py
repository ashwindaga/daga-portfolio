import json, time, requests
H = {"User-Agent": "Mozilla/5.0"}
def get(url):
    for i in range(3):
        try:
            r = requests.get(url, timeout=20, headers=H); r.raise_for_status(); return r.json()
        except Exception as e:
            err = e; time.sleep(2)
    return {"error": str(err)}
QUERIES = ["SBI Focused", "ICICI Prudential Value", "HDFC Children", "ICICI Prudential Balanced Advantage",
           "ICICI Prudential Nifty Next 50 Index", "Parag Parikh Flexi Cap", "Canara Robeco Flexi Cap",
           "Mirae Asset Aggressive Hybrid", "Motilal Oswal Flexi Cap"]
for q in QUERIES:
    print(f"\n=== search: {q}")
    res = get("https://api.mfapi.in/mf/search?q=" + requests.utils.quote(q))
    if isinstance(res, dict): print(res); continue
    for s in res:
        n = s["schemeName"]
        if "IDCW" in n.upper() or "DIVIDEND" in n.upper() or "BONUS" in n.upper(): continue
        print(s["schemeCode"], "|", n)
print("\n=== latest for configured codes")
for c in [118825,120662,104908,120716,120599,120620,101922,102414,133839,147794,118834]:
    d = get(f"https://api.mfapi.in/mf/{c}/latest")
    print(c, "|", json.dumps(d)[:400])
