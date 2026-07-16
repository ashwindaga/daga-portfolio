"""
Daga Family Portfolio -- SIP Auto-Updater
==========================================
Usage:
  python update_sips.py                        # normal monthly SIP update
  python update_sips.py --lumpsum              # record a one-off lumpsum purchase
  python update_sips.py --stop-sip             # mark a SIP as stopped
  python update_sips.py --add-sip              # add a new SIP
  python update_sips.py --change-sip-amount    # change an existing SIP amount

Requirements:
  pip install requests pyxirr
"""

import json
import sys
import requests
from datetime import date, timedelta
from pathlib import Path
from pyxirr import xirr as compute_xirr

BASE_DIR = Path(__file__).parent

# ── Live SIP Configuration ────────────────────────────────────────────────────

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

STAMP_DUTY_RATE = 0.00005
_nav_cache = {}


# ── NAV Fetching ──────────────────────────────────────────────────────────────

def fetch_nav(amfi_scheme, nav_date):
    """Fetch historical NAV from mfapi.in for a given scheme and date.
    Returns (nav, actual_allotment_date) rolling forward for non-trading days."""
    cache_key = (amfi_scheme, nav_date)
    if cache_key in _nav_cache:
        return _nav_cache[cache_key]

    start = nav_date.strftime("%Y-%m-%d")
    end   = (nav_date + timedelta(days=7)).strftime("%Y-%m-%d")
    url   = f"https://api.mfapi.in/mf/{amfi_scheme}?startDate={start}&endDate={end}"

    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise ValueError("No internet connection. Check your network and try again.")
    except requests.exceptions.Timeout:
        raise ValueError("mfapi.in timed out. Try again in a few minutes.")
    except requests.exceptions.HTTPError as e:
        raise ValueError(f"mfapi.in returned error: {e}")

    try:
        data = resp.json()
    except Exception:
        raise ValueError(f"mfapi.in returned invalid data for scheme {amfi_scheme}.")

    if data.get("status") != "SUCCESS" or not data.get("data"):
        raise ValueError(
            f"No NAV data for scheme {amfi_scheme} between {start} and {end}. "
            f"Verify the scheme code in LIVE_SIPS config."
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
        f"No trading day found for scheme {amfi_scheme} within 7 days of {nav_date}. "
        f"Market may have been closed for an extended period."
    )


def fetch_latest_nav(amfi_scheme):
    """Fetch the most recent NAV from mfapi.in /latest endpoint."""
    cache_key = ("latest", amfi_scheme)
    if cache_key in _nav_cache:
        return _nav_cache[cache_key]

    url = f"https://api.mfapi.in/mf/{amfi_scheme}/latest"
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "SUCCESS" or not data.get("data"):
            raise ValueError(f"No latest NAV for scheme {amfi_scheme}")
        nav = float(data["data"][0]["nav"])
        _nav_cache[cache_key] = nav
        return nav
    except Exception as e:
        raise ValueError(f"Could not fetch latest NAV for scheme {amfi_scheme}: {e}")


# ── Ledger Helpers ────────────────────────────────────────────────────────────

def load_ledger(person):
    path = BASE_DIR / LEDGER_FILES[person]
    if not path.exists():
        print(f"\n  ⚠️  Ledger file not found: {path.name}")
        print(f"      Make sure all JSON files are in the same folder as update_sips.py")
        sys.exit(1)
    try:
        with open(path) as f:
            data = json.load(f)
        return [t for t in data if t is not None]
    except json.JSONDecodeError as e:
        print(f"\n  ⚠️  Corrupt JSON in {path.name}: {e}")
        print(f"      Download a fresh copy from GitHub and try again.")
        sys.exit(1)


def save_ledger(person, txns):
    path = BASE_DIR / LEDGER_FILES[person]
    try:
        with open(path, "w") as f:
            json.dump(txns, f, indent=2)
    except PermissionError:
        print(f"\n  ⚠️  Cannot write to {path.name} -- is the file open in another program?")
        sys.exit(1)
    except OSError as e:
        print(f"\n  ⚠️  Failed to save {path.name}: {e}")
        sys.exit(1)


def load_metrics(person):
    path = BASE_DIR / METRICS_FILES[person]
    if not path.exists():
        print(f"\n  ⚠️  Metrics file not found: {path.name}")
        print(f"      Make sure all JSON files are in the same folder as update_sips.py")
        sys.exit(1)
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"\n  ⚠️  Corrupt JSON in {path.name}: {e}")
        sys.exit(1)


def save_metrics(person, data):
    path = BASE_DIR / METRICS_FILES[person]
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except (PermissionError, OSError) as e:
        print(f"\n  ⚠️  Failed to save {path.name}: {e}")
        sys.exit(1)


def last_sip_date(txns, scheme):
    dates = [
        date.fromisoformat(t["date"])
        for t in txns
        if t.get("scheme") == scheme and t.get("type") == "SIP"
    ]
    return max(dates) if dates else None


def sip_due_dates_since(last_date, sip_day, up_to, stopped_after=None):
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
                nav = fetch_latest_nav(amfi_lookup[scheme])
                cur_value = round(units * nav, 2)
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
    if not html_path.exists():
        print(f"  ⚠️  Dashboard HTML not found: {html_path.name}")
        print(f"      Make sure daga_family_portfolio.html is in the same folder.")
        return

    try:
        with open(html_path) as f:
            html = f.read()
    except OSError as e:
        print(f"  ⚠️  Could not read dashboard HTML: {e}")
        return

    # Replace DATA block using string splitting (regex breaks on nested JSON)
    data_json = (
        "const DATA = {\n"
        "  Daksh: " + json.dumps(all_metrics["Daksh"]) + ",\n"
        "  Kush: "  + json.dumps(all_metrics["Kush"])  + ",\n"
        "  Ashwin: "+ json.dumps(all_metrics["Ashwin"])+ "\n"
        "};"
    )
    idx_s = html.find("const DATA = {")
    if idx_s == -1:
        print("  ⚠️  Could not find DATA block in HTML -- dashboard not updated!")
        return
    idx_e = html.find("\n};", idx_s) + len("\n};")
    html = html[:idx_s] + data_json + html[idx_e:]

    # Build RECENT_TXNS and ACTIVE_SIPS
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

    try:
        with open(html_path, "w") as f:
            f.write(html)
        print(f"  Dashboard rebuilt: {html_path.name}")
    except (PermissionError, OSError) as e:
        print(f"  ⚠️  Could not write dashboard HTML: {e}")
        print(f"      Is daga_family_portfolio.html open in a browser? Close and retry.")


# ── Interactive Helpers ───────────────────────────────────────────────────────

def cmd_lumpsum():
    """Interactively record a one-off lumpsum purchase."""
    print("\n── Record Lumpsum Purchase ──")

    person = input("Person (Daksh / Kush / Ashwin): ").strip()
    if person not in LEDGER_FILES:
        print(f"Unknown person '{person}'. Must be exactly: Daksh, Kush, or Ashwin")
        return

    txns = load_ledger(person)
    schemes = sorted(set(t["scheme"] for t in txns if t.get("scheme")))
    print(f"\nAvailable schemes for {person}:")
    for i, s in enumerate(schemes, 1):
        print(f"  {i}. {s}")

    choice = input("\nEnter number: ").strip()
    try:
        scheme = schemes[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid choice."); return

    gross_str = input("Gross amount (Rs): ").strip()
    try:
        gross = float(gross_str)
        if gross <= 0:
            print("Amount must be greater than zero."); return
    except ValueError:
        print(f"Invalid amount '{gross_str}'. Enter a number e.g. 50000"); return

    date_str = input("Investment date (YYYY-MM-DD): ").strip()
    try:
        inv_date = date.fromisoformat(date_str)
        if inv_date > date.today():
            print("Date cannot be in the future."); return
    except ValueError:
        print(f"Invalid date '{date_str}'. Use format YYYY-MM-DD e.g. 2026-07-15"); return

    amfi_str = input("AMFI scheme code (press Enter to use from SIP config): ").strip()
    if amfi_str:
        try:
            amfi_scheme = int(amfi_str)
        except ValueError:
            print(f"Invalid scheme code '{amfi_str}'. Must be a number."); return
    else:
        match = next((s for s in LIVE_SIPS if s["scheme"] == scheme and s["person"] == person), None)
        if match:
            amfi_scheme = match["amfi_scheme"]
        else:
            print("Scheme not in SIP config. Please enter the AMFI scheme code manually.")
            try:
                amfi_scheme = int(input("AMFI scheme code: ").strip())
            except ValueError:
                print("Invalid scheme code."); return

    print(f"\nFetching NAV for {inv_date}...")
    try:
        nav, allotment_date = fetch_nav(amfi_scheme, inv_date)
    except ValueError as e:
        print(f"  ⚠️  Could not fetch NAV: {e}"); return

    net, units, stamp = stamp_duty_and_units(gross, nav)
    folio = next(
        (t["folio"] for t in txns if t.get("scheme") == scheme and t.get("folio")),
        "UNKNOWN"
    )

    print(f"\n  Allotment date : {allotment_date}")
    print(f"  NAV            : {nav}")
    print(f"  Gross amount   : Rs {gross:,.2f}")
    print(f"  Stamp duty     : Rs {stamp:,.2f}")
    print(f"  Net amount     : Rs {net:,.2f}")
    print(f"  Units allotted : {units:.3f}")

    confirm = input("\nConfirm and save? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled."); return

    txn = {
        "person": person, "folio": folio, "scheme": scheme,
        "type": "Lumpsum Purchase", "date": allotment_date.isoformat(),
        "amount": net, "nav": nav, "units": units,
        "sip_series": None,
        "note": (
            f"Lumpsum-added by update_sips.py on {date.today()}. "
            f"Gross {gross}, stamp duty {stamp}."
        ),
    }
    txns.append(txn)
    save_ledger(person, txns)
    print(f"\n✅ Lumpsum recorded successfully.")
    print(f"   Run 'python update_sips.py' to rebuild the dashboard with updated metrics.")


def cmd_stop_sip():
    """Interactively mark a SIP as stopped."""
    print("\n── Stop a SIP ──")
    active = [(i, s) for i, s in enumerate(LIVE_SIPS) if s.get("active", True)]
    if not active:
        print("No active SIPs found."); return
    for i, (idx, s) in enumerate(active, 1):
        print(f"  {i}. {s['person']:<8} | {s['scheme'][:50]:<52} | Rs {s['sip_amount_gross']:,}/mo")

    try:
        choice   = int(input("\nEnter number to stop: ").strip()) - 1
        sip_idx  = active[choice][0]
    except (ValueError, IndexError):
        print("Invalid choice."); return

    stopped_date = input("Last SIP date processed (YYYY-MM-DD): ").strip()
    try:
        date.fromisoformat(stopped_date)
    except ValueError:
        print(f"Invalid date '{stopped_date}'. Use format YYYY-MM-DD."); return

    LIVE_SIPS[sip_idx]["active"] = False
    LIVE_SIPS[sip_idx]["stopped_after"] = stopped_date
    print(f"\n✅ SIP marked as stopped after {stopped_date} for this run.")
    print("   To make permanent: share details with Claude to update update_sips.py")


def cmd_add_sip():
    """Interactively add a new SIP."""
    print("\n── Add a New SIP ──")
    person = input("Person (Daksh / Kush / Ashwin): ").strip()
    if person not in LEDGER_FILES:
        print(f"Unknown person '{person}'."); return

    scheme      = input("Scheme name (must match ledger exactly): ").strip()
    folio       = input("Folio number: ").strip()

    try:
        sip_day = int(input("SIP date (day of month, e.g. 15): ").strip())
        if not 1 <= sip_day <= 31:
            print("Day must be between 1 and 31."); return
        gross = float(input("SIP amount gross (Rs): ").strip())
        if gross <= 0:
            print("Amount must be greater than zero."); return
        amfi_amc    = int(input("AMFI AMC code: ").strip())
        amfi_scheme = int(input("AMFI scheme code: ").strip())
    except ValueError:
        print("Invalid input -- numbers only for day, amount, and codes."); return

    sip_series = input("SIP series label (e.g. SIP-1 (live)): ").strip()
    start_date = input("First SIP date (YYYY-MM-DD): ").strip()
    try:
        date.fromisoformat(start_date)
    except ValueError:
        print(f"Invalid date '{start_date}'. Use format YYYY-MM-DD."); return

    new_sip = {
        "person": person, "scheme": scheme, "folio": folio,
        "sip_day": sip_day, "sip_amount_gross": gross,
        "amfi_amc": amfi_amc, "amfi_scheme": amfi_scheme,
        "sip_series": sip_series, "active": True,
        "effective_from": start_date,
    }
    print(f"\n  Will add:\n{json.dumps(new_sip, indent=4)}")
    confirm = input("\nConfirm? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled."); return

    LIVE_SIPS.append(new_sip)
    print("\n✅ New SIP added for this run.")
    print("   To make permanent: share details with Claude to update update_sips.py")


def cmd_change_sip_amount():
    """Interactively change the amount of an existing SIP."""
    print("\n── Change SIP Amount ──")
    active = [(i, s) for i, s in enumerate(LIVE_SIPS) if s.get("active", True)]
    if not active:
        print("No active SIPs found."); return
    for i, (idx, s) in enumerate(active, 1):
        print(f"  {i}. {s['person']:<8} | {s['scheme'][:50]:<52} | Rs {s['sip_amount_gross']:,}/mo")

    try:
        choice   = int(input("\nEnter number to change: ").strip()) - 1
        sip_idx  = active[choice][0]
        new_gross = float(input("New gross SIP amount (Rs): ").strip())
        if new_gross <= 0:
            print("Amount must be greater than zero."); return
    except (ValueError, IndexError):
        print("Invalid input."); return

    eff_from = input("Effective from date (YYYY-MM-DD, first instalment at new amount): ").strip()
    try:
        date.fromisoformat(eff_from)
    except ValueError:
        print(f"Invalid date '{eff_from}'. Use format YYYY-MM-DD."); return

    old_amt = LIVE_SIPS[sip_idx]["sip_amount_gross"]
    print(f"\n  Changing Rs {old_amt:,} → Rs {new_gross:,} from {eff_from}")
    confirm = input("Confirm? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled."); return

    LIVE_SIPS[sip_idx]["sip_amount_gross"] = new_gross
    LIVE_SIPS[sip_idx]["amount_changed_from"] = eff_from
    print("\n✅ SIP amount updated for this run.")
    print("   To make permanent: share details with Claude to update update_sips.py")


# ── Main SIP Update ───────────────────────────────────────────────────────────

def main_update():
    today   = date.today()
    ledgers = {p: load_ledger(p) for p in ["Daksh", "Kush", "Ashwin"]}
    new_txn_count = 0

    print(f"\nDaga Family SIP Updater — running as of {today}")
    print("=" * 60)

    for sip in LIVE_SIPS:
        if not sip.get("active", True):
            print(f"  ⏸  {sip['person']:<8}| {sip['scheme'][:45]:<46}| STOPPED")
            continue

        person = sip["person"]
        scheme = sip["scheme"]
        txns   = ledgers[person]

        last_date = last_sip_date(txns, scheme)
        if last_date is None:
            print(f"  ⚠️  No existing SIP found for {scheme} — skipping")
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
            except ValueError as e:
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
                f"NAV {nav:.4f} | Units {units:.3f} | Net Rs {net:,.2f}"
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
        existing = load_metrics(person)
        updated  = recompute_metrics(person, ledgers[person], existing)
        save_metrics(person, updated)
        all_metrics[person] = updated
        print(
            f"  {person}: Rs {updated['total_invested']:,.0f} invested → "
            f"Rs {updated['total_current_value']:,.0f} current | "
            f"XIRR {updated['total_xirr_pct']:.2f}%"
        )

    print("\nRebuilding dashboard...")
    rebuild_dashboard(all_metrics, ledgers)

    if new_txn_count > 0:
        print("\nSummary of new transactions added:")
        print(f"{'Person':<8}{'Fund':<44}{'Due Date':<12}{'Allotment':<12}{'NAV':>10}{'Units':>8}")
        print("-" * 96)
        for person, txns in ledgers.items():
            for t in txns:
                note = t.get("note") or ""
                if note.startswith("Auto-added") and str(today) in note:
                    fund = t["scheme"].split(" - ")[0][:43]
                    due  = note.split("SIP due ")[1].split(",")[0] if "SIP due" in note else t["date"]
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
