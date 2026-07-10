"""
Daga Family Portfolio -- SIP Auto-Updater
==========================================
Run this script monthly (or whenever you want to catch up).

Usage:
  python update_sips.py                        # normal monthly SIP update
  python update_sips.py --lumpsum              # record a one-off lumpsum purchase
  python update_sips.py --stop-sip             # mark a SIP as stopped
  python update_sips.py --add-sip              # add a new SIP
  python update_sips.py --change-sip-amount    # change an existing SIP amount

Requirements:
  pip install requests pyxirr

All files must be in the same folder as this script:
  daksh_transaction_ledger.json / kush_transaction_ledger.json / ashwin_transaction_ledger.json
  daksh_metrics_summary.json / kush_metrics_summary.json / ashwin_metrics_summary.json
  daga_family_portfolio.html
"""

import json
import sys
import requests
from datetime import date, timedelta
from pathlib import Path
from pyxirr import xirr as compute_xirr

BASE_DIR = Path(__file__).parent

# ── Live SIP Configuration ────────────────────────────────────────────────────
# To stop a SIP:           set "active": False and add "stopped_after": "YYYY-MM-DD"
# To change SIP amount:    add a new entry with same scheme + new sip_amount_gross + "effective_from": "YYYY-MM-DD"
#                          and set "active": False on the old entry
# To add a new SIP:        append a new dict below

LIVE_SIPS = [
    {
        "person": "Daksh",
        "scheme": "Mirae Asset Large Cap Fund - Direct Plan Growth",
        "folio": "29975080",
        "sip_day": 20,
        "sip_amount_gross": 6000,
        "amfi_amc": 45,
        "amfi_scheme": 118825,
        "sip_series": "SIP-2 (live)",
        "active": True,
    },
    {
        "person": "Daksh",
        "scheme": "UTI Flexi Cap Fund - Direct Plan Growth",
        "folio": "505348365526",
        "sip_day": 20,
        "sip_amount_gross": 6000,
        "amfi_amc": 52,
        "amfi_scheme": 120662,
        "sip_series": "SIP (live)",
        "active": True,
    },
    {
        "person": "Daksh",
        "scheme": "Kotak Midcap Fund - Growth (Regular Plan)",
        "folio": "10588849",
        "sip_day": 28,
        "sip_amount_gross": 6000,
        "amfi_amc": 17,
        "amfi_scheme": 104908,
        "sip_series": "SIP (live)",
        "active": True,
    },
    {
        "person": "Daksh",
        "scheme": "UTI Nifty 50 Index Fund - Direct Plan Growth",
        "folio": "505348365526",
        "sip_day": 28,
        "sip_amount_gross": 5000,
        "amfi_amc": 52,
        "amfi_scheme": 120716,
        "sip_series": "SIP (live)",
        "active": True,
    },
    {
        "person": "Kush",
        "scheme": "ICICI Prudential Multicap Fund - Direct Plan Growth",
        "folio": "17046950/72",
        "sip_day": 15,
        "sip_amount_gross": 6000,
        "amfi_amc": 12,
        "amfi_scheme": 120599,
        "sip_series": "SIP (live)",
        "active": True,
    },
    {
        "person": "Kush",
        "scheme": "ICICI Prudential Nifty 50 Index Fund - Direct Plan Growth",
        "folio": "17046950/72",
        "sip_day": 7,
        "sip_amount_gross": 5000,
        "amfi_amc": 12,
        "amfi_scheme": 120620,
        "sip_series": "SIP (live)",
        "active": True,
    },
    {
        "person": "Kush",
        "scheme": "Canara Robeco Flexi Cap Fund - Regular Plan Growth",
        "folio": "17742075881",
        "sip_day": 4,
        "sip_amount_gross": 6000,
        "amfi_amc": 20,
        "amfi_scheme": 101922,
        "sip_series": "SIP-2 (live)",
        "active": True,
    },
    {
        "person": "Kush",
        "scheme": "SBI Contra Fund - Regular Plan Growth",
        "folio": "30141876",
        "sip_day": 4,
        "sip_amount_gross": 6000,
        "amfi_amc": 3,
        "amfi_scheme": 102414,
        "sip_series": "SIP-2 (live)",
        "active": True,
    },
    {
        "person": "Ashwin",
        "scheme": "PGIM India Flexi Cap Fund - Direct Plan Growth",
        "folio": "91016971423",
        "sip_day": 15,
        "sip_amount_gross": 10000,
        "amfi_amc": 44,
        "amfi_scheme": 133839,
        "sip_series": "SIP (live)",
        "active": True,
    },
    {
        "person": "Ashwin",
        "scheme": "Motilal Oswal Nifty 50 Index Fund - Direct Plan Growth",
        "folio": "9018506334",
        "sip_day": 2,
        "sip_amount_gross": 7500,
        "amfi_amc": 40,
        "amfi_scheme": 147794,
        "sip_series": "SIP (live)",
        "active": True,
    },
    {
        "person": "Ashwin",
        "scheme": "Mirae Asset Large and Midcap Fund - Direct Plan Growth",
        "folio": "79914164382",
        "sip_day": 28,
        "sip_amount_gross": 10000,
        "amfi_amc": 45,
        "amfi_scheme": 118834,
        "sip_series": "SIP-2 (live)",
        "active": True,
    },
]

LEDGER_FILES = {
    "Daksh":  "daksh_transaction_ledger.json",
    "Kush":   "kush_transaction_ledger.json",
    "Ashwin": "ashwin_transaction_ledger.json",
}
METRICS_FILES = {
    "Daksh":  "daksh_metrics_summary.json",
    "Kush":   "kush_metrics_summary.json",
    "Ashwin": "ashwin_metrics_summary.json",
}

STAMP_DUTY_RATE = 0.00005  # 0.005%
_nav_cache = {}


# ── NAV Fetching ──────────────────────────────────────────────────────────────

def fetch_nav(amfi_scheme, nav_date):
    """Fetch historical NAV from mfapi.in for a given scheme code and date.
    If nav_date is a non-trading day, returns the next available trading day."""

    cache_key = (amfi_scheme, nav_date)
    if cache_key in _nav_cache:
        return _nav_cache[cache_key]

    start = nav_date.strftime("%Y-%m-%d")
    end   = (nav_date + timedelta(days=7)).strftime("%Y-%m-%d")
    url   = f"https://api.mfapi.in/mf/{amfi_scheme}?startDate={start}&endDate={end}"

    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()

    data = resp.json()
    if data.get("status") != "SUCCESS" or not data.get("data"):
        raise ValueError(
            f"No data from mfapi for scheme {amfi_scheme} between {start} and {end}. "
            f"Check the scheme code."
        )

    nav_by_date = {}
    for entry in data["data"]:
        try:
            d = date(*(int(x) for x in reversed(entry["date"].split("-"))))
            nav_by_date[d] = float(entry["nav"])
        except (ValueError, KeyError):
            continue

    for delta in range(8):
        candidate = nav_date + timedelta(days=delta)
        if candidate in nav_by_date:
            result = (nav_by_date[candidate], candidate)
            _nav_cache[cache_key] = result
            return result

    raise ValueError(
        f"No trading day found for scheme {amfi_scheme} within 7 days of {nav_date}."
    )


def fetch_latest_nav(amfi_scheme):
    """Fetch the most recent available NAV from mfapi.in (no date needed).
    Uses the /latest endpoint which always returns the last published NAV."""
    if amfi_scheme in _nav_cache.get("latest", {}):
        return _nav_cache["latest"][amfi_scheme]

    url = f"https://api.mfapi.in/mf/{amfi_scheme}/latest"
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "SUCCESS" or not data.get("data"):
        raise ValueError(f"No latest NAV for scheme {amfi_scheme}")
    nav = float(data["data"][0]["nav"])
    if "latest" not in _nav_cache:
        _nav_cache["latest"] = {}
    _nav_cache["latest"][amfi_scheme] = nav
    return nav


def fetch_nav_by_scheme_name(scheme_name, nav_date):
    """Look up the mfapi scheme code from LIVE_SIPS config and fetch NAV."""
    match = next((s for s in LIVE_SIPS if s["scheme"] == scheme_name), None)
    if not match:
        raise ValueError(
            f"Scheme '{scheme_name}' not found in LIVE_SIPS config. "
            f"Add it first with --add-sip."
        )
    return fetch_nav(match["amfi_scheme"], nav_date)


# ── Ledger Helpers ────────────────────────────────────────────────────────────

def load_ledger(person):
    path = BASE_DIR / LEDGER_FILES[person]
    with open(path) as f:
        return [t for t in json.load(f) if t is not None]

def save_ledger(person, txns):
    path = BASE_DIR / LEDGER_FILES[person]
    with open(path, "w") as f:
        json.dump(txns, f, indent=2)

def last_sip_date(txns, scheme):
    dates = [
        date.fromisoformat(t["date"])
        for t in txns
        if t.get("scheme") == scheme and t.get("type") == "SIP"
    ]
    return max(dates) if dates else None

def sip_due_dates_since(last_date, sip_day, up_to, stopped_after=None):
    """Return calendar due dates for a SIP since last_date up to up_to."""
    import calendar
    due = []
    y, m = last_date.year, last_date.month
    while True:
        m += 1
        if m > 12:
            m = 1
            y += 1
        last_day = calendar.monthrange(y, m)[1]
        d = date(y, m, min(sip_day, last_day))
        if d > up_to:
            break
        if stopped_after and d > stopped_after:
            break
        due.append(d)
    return due

def stamp_duty_and_units(gross, nav):
    stamp = round(gross * STAMP_DUTY_RATE, 2)
    net   = gross - stamp
    units = round(net / nav, 3)
    return net, units, stamp


# ── Metrics Recompute ─────────────────────────────────────────────────────────

def recompute_metrics(person, txns, existing_metrics):
    as_of = date.today()
    amfi_lookup = {
        s["scheme"]: s["amfi_scheme"]
        for s in LIVE_SIPS if s["person"] == person
    }
    schemes_meta = {s["scheme"]: s for s in existing_metrics["schemes"]}
    updated_schemes = []
    all_cf_dates, all_cf_amounts = [], []

    for scheme, meta in schemes_meta.items():
        rows = [t for t in txns if t.get("scheme") == scheme]
        if not rows:
            updated_schemes.append(meta)
            continue

        invested = sum(t["amount"] for t in rows if t["amount"] > 0)
        redeemed = -sum(t["amount"] for t in rows if t["amount"] < 0)
        units    = sum(t["units"]  for t in rows)

        if meta["status"] == "live" and scheme in amfi_lookup:
            try:
                cur_value = round(units * fetch_latest_nav(amfi_lookup[scheme]), 2)
            except Exception:
                cur_value = meta["current_value"]
        else:
            cur_value = meta["current_value"]

        cf_d = [date.fromisoformat(t["date"]) for t in rows]
        cf_a = [-t["amount"] for t in rows]
        try:
            irr = compute_xirr(cf_d + [as_of], cf_a + [cur_value]) * 100
        except Exception:
            irr = meta.get("xirr_pct", float("nan"))

        abs_ret = (cur_value + redeemed - invested) / invested * 100
        updated = dict(meta)
        updated.update({
            "invested": invested, "units": units,
            "current_value": cur_value,
            "abs_return_pct": abs_ret, "xirr_pct": irr,
        })
        updated_schemes.append(updated)
        all_cf_dates.extend(cf_d)
        all_cf_amounts.extend(cf_a)

    total_invested = sum(s.get("invested", 0) for s in updated_schemes)
    total_current  = sum(s.get("current_value", 0) for s in updated_schemes)
    try:
        port_xirr = compute_xirr(
            all_cf_dates + [as_of], all_cf_amounts + [total_current]
        ) * 100
    except Exception:
        port_xirr = existing_metrics.get("total_xirr_pct", float("nan"))

    return {
        "as_of": as_of.isoformat(),
        "person": person,
        "dob": existing_metrics.get("dob"),
        "schemes": updated_schemes,
        "total_invested": total_invested,
        "total_current_value": total_current,
        "total_abs_return_pct": (total_current - total_invested) / total_invested * 100,
        "total_xirr_pct": port_xirr,
    }


# ── Dashboard Rebuild ─────────────────────────────────────────────────────────

def rebuild_dashboard(all_metrics, all_ledgers):
    html_path = BASE_DIR / "daga_family_portfolio.html"
    with open(html_path) as f:
        html = f.read()

    # ── Replace DATA block ──────────────────────────────────────────────────
    # Use string splitting -- regex breaks on nested JSON braces.
    data_json = (
        "const DATA = {\n"
        "  Daksh: " + json.dumps(all_metrics["Daksh"]) + ",\n"
        "  Kush: "  + json.dumps(all_metrics["Kush"])  + ",\n"
        "  Ashwin: "+ json.dumps(all_metrics["Ashwin"])+ "\n"
        "};"
    )

    idx_s = html.find("const DATA = {")
    if idx_s == -1:
        print("  WARNING: Could not find DATA block -- dashboard not updated!")
        return
    # The DATA block closes with "\n};" on its own line
    idx_e = html.find("\n};", idx_s) + len("\n};")
    html = html[:idx_s] + data_json + html[idx_e:]

    # ── Build RECENT_TXNS and ACTIVE_SIPS ──────────────────────────────────
    recent = []
    for person, txns in all_ledgers.items():
        for t in txns:
            note = t.get("note") or ""
            if note.startswith("Auto-added") or note.startswith("Lumpsum-added"):
                recent.append(t)
    recent.sort(key=lambda t: t["date"], reverse=True)
    active_sips = [s for s in LIVE_SIPS if s.get("active", True)]

    txns_block = (
        "const RECENT_TXNS = " + json.dumps(recent) + ";\n"
        "const ACTIVE_SIPS = " + json.dumps(active_sips) + ";"
    )

    if "const RECENT_TXNS" in html:
        r_s = html.find("const RECENT_TXNS")
        r_e = html.find(";", html.find("const ACTIVE_SIPS")) + 1
        html = html[:r_s] + txns_block + html[r_e:]
    else:
        html = html.replace("const inr", txns_block + "\n\nconst inr", 1)

    with open(html_path, "w") as f:
        f.write(html)
    print(f"  Dashboard rebuilt: {html_path.name}")


def main_update():
    today   = date.today()
    ledgers = {p: load_ledger(p) for p in ["Daksh", "Kush", "Ashwin"]}
    new_txn_count = 0

    print(f"\nDaga Family SIP Updater — running as of {today}")
    print("=" * 60)

    for sip in LIVE_SIPS:
        if not sip.get("active", True):
            print(f"  ⏸  {sip['person']} | {sip['scheme'][:45]} | STOPPED")
            continue

        person = sip["person"]
        scheme = sip["scheme"]
        txns   = ledgers[person]

        last_date = last_sip_date(txns, scheme)
        if last_date is None:
            print(f"  WARNING: No existing SIP found for {scheme} — skipping")
            continue

        stopped_after = sip.get("stopped_after")
        stopped_date  = date.fromisoformat(stopped_after) if stopped_after else None
        due_dates = sip_due_dates_since(last_date, sip["sip_day"], today, stopped_date)

        if not due_dates:
            print(f"  {person:<8}| {scheme[:45]:<46}| up to date (last: {last_date})")
            continue

        print(f"\n  {person} | {scheme}")
        print(f"    Last recorded: {last_date} | New instalments: {len(due_dates)}")

        for due_date in due_dates:
            try:
                nav, allotment_date = fetch_nav(sip["amfi_scheme"], due_date)
            except Exception as e:
                print(f"    ⚠️  Could not fetch NAV for {due_date}: {e}")
                continue

            net, units, stamp = stamp_duty_and_units(sip["sip_amount_gross"], nav)
            txn = {
                "person": person, "folio": sip["folio"], "scheme": scheme,
                "type": "SIP", "date": allotment_date.isoformat(),
                "amount": net, "nav": nav, "units": units,
                "sip_series": sip["sip_series"],
                "note": (
                    f"Auto-added by update_sips.py on {today}. "
                    f"SIP due {due_date}, allotted {allotment_date}. "
                    f"Gross {sip['sip_amount_gross']}, stamp duty {stamp}."
                ),
            }
            txns.append(txn)
            new_txn_count += 1
            print(
                f"    ✓ {due_date} → allotted {allotment_date} | "
                f"NAV {nav:.4f} | Units {units:.3f} | Net ₹{net:,.2f}"
            )

    if new_txn_count == 0:
        print("\n  All SIPs are up to date. Nothing to add.")
    else:
        print(f"\n  Total new transactions: {new_txn_count}")

    print("\n" + "=" * 60)
    print("Saving ledgers...")
    for person, txns in ledgers.items():
        save_ledger(person, txns)
        print(f"  {person}: {len(txns)} transactions saved")

    print("\nRecomputing metrics...")
    all_metrics = {}
    for person in ["Daksh", "Kush", "Ashwin"]:
        mp = BASE_DIR / METRICS_FILES[person]
        with open(mp) as f:
            existing = json.load(f)
        updated = recompute_metrics(person, ledgers[person], existing)
        with open(mp, "w") as f:
            json.dump(updated, f, indent=2)
        all_metrics[person] = updated
        print(
            f"  {person}: ₹{updated['total_invested']:,.0f} invested → "
            f"₹{updated['total_current_value']:,.0f} current | "
            f"XIRR {updated['total_xirr_pct']:.2f}%"
        )

    print("\nRebuilding dashboard...")
    rebuild_dashboard(all_metrics, ledgers)

    # Summary table
    if new_txn_count > 0:
        print("\nSummary of new transactions added:")
        print(f"{'Person':<8}{'Fund':<44}{'Due Date':<12}{'Allotment':<12}{'NAV':>10}{'Units':>8}")
        print("-" * 96)
        for person, txns in ledgers.items():
            for t in txns:
                note = t.get("note") or ""
                if note.startswith("Auto-added") or note.startswith("Lumpsum-added"):
                    if str(today) in note:
                        fund  = t["scheme"].split(" - ")[0][:43]
                        if "SIP due" in note:
                            due = note.split("SIP due ")[1].split(",")[0]
                        else:
                            due = t["date"]
                        print(
                            f"{t['person']:<8}{fund:<44}{due:<12}"
                            f"{t['date']:<12}{t['nav']:>10.4f}{t['units']:>8.3f}"
                        )

    print("\n✅ Done. Open daga_family_portfolio.html to see the updated dashboard.")


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--lumpsum" in args:
        cmd_lumpsum()
    elif "--stop-sip" in args:
        cmd_stop_sip()
    elif "--add-sip" in args:
        cmd_add_sip()
    elif "--change-sip-amount" in args:
        cmd_change_sip_amount()
    else:
        main_update()
