# cms_watch.py
# Purpose: Pull CMS NH/LTCH/IRF/HHA snippets and emit a "what's new" changelog by CCN.
# Author: Mitch Coplan
# Usage (example at bottom):
#   python cms_watch.py --ccn 455682 675791 676336 --days 60

import os
import json
import time
import math
import glob
import argparse
import datetime as dt
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import requests
import pandas as pd
from dateutil import tz
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# -----------------------------
# Config: dataset IDs (CMS PDC / Socrata). These can change; override via env if needed.
# -----------------------------
# Nursing Home Penalties (Civil Money Penalties + DPNA)
DATASET_PENALTIES = os.getenv("CMS_DATASET_PENALTIES", "g6vv-u9sr")
# Nursing Home Health Deficiencies (F-tags)
DATASET_DEFICIENCIES = os.getenv("CMS_DATASET_DEFICIENCIES", "y2hd-3m6z")
# Nursing Home Provider Info (stars, staffing, turnover, weekend staffing, last inspection)
DATASET_PROVIDER_INFO = os.getenv("CMS_DATASET_PROVIDER_INFO", "4pq5-n9py")
# SNF QRP provider-level (discharge to community, readmits, MSPB-PAC, etc.)
DATASET_SNF_QRP = os.getenv("CMS_DATASET_SNF_QRP", "v2vd-humh")  # placeholder; adjust if CMS updates
# SNF VBP facility-level (incentive payment multiplier, rank)
DATASET_SNF_VBP = os.getenv("CMS_DATASET_SNF_VBP", "m2qk-2p5h")  # placeholder; adjust if CMS updates

PDC_BASE = "https://data.cms.gov/resource"
APP_TOKEN = os.getenv("CMS_PDC_APP_TOKEN")  # Strongly recommended for higher rate limits

# Output + snapshot dirs
SNAP_DIR = Path("data/snapshots")
OUT_DIR = Path("outputs_watch")
SNAP_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Socrata GET helper with pagination + retries
# -----------------------------
class SocrataError(Exception):
    pass

@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(SocrataError),
)
def _socrata_get(dataset_id: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = f"{PDC_BASE}/{dataset_id}.json"
    headers = {"Accept": "application/json"}
    if APP_TOKEN:
        headers["X-App-Token"] = APP_TOKEN

    # Pagination
    limit = params.get("$limit", 50000)
    offset = 0
    all_rows: List[Dict[str, Any]] = []

    while True:
        p = dict(params)
        p["$limit"] = limit
        p["$offset"] = offset

        resp = requests.get(url, headers=headers, params=p, timeout=60)
        if resp.status_code in (429, 500, 502, 503, 504):
            raise SocrataError(f"Transient error {resp.status_code}: {resp.text[:200]}")
        if resp.status_code != 200:
            raise Exception(f"Socrata request failed [{resp.status_code}]: {resp.text[:200]}")

        rows = resp.json()
        if not isinstance(rows, list):
            raise Exception(f"Unexpected response format: {rows}")

        all_rows.extend(rows)
        if len(rows) < limit:
            break
        offset += limit
        # polite pacing
        time.sleep(0.2)

    return all_rows

def _to_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Normalize CCN field (common variations)
    for c in ["federal_provider_number", "ccn", "provider_number"]:
        if c in df.columns:
            df["ccn"] = df[c].astype(str).str.zfill(6)
            break
    if "ccn" not in df.columns:
        # will be joined later by caller if needed
        pass
    return df

# -----------------------------
# Fetchers (by dataset)
# -----------------------------
def fetch_penalties(ccns: List[str], since_iso: Optional[str]) -> pd.DataFrame:
    where_clause = f"federal_provider_number in ({','.join([repr(x) for x in ccns])})"
    if since_iso:
        where_clause += f" AND imposed_date >= '{since_iso}'"
    rows = _socrata_get(DATASET_PENALTIES, {
        "$select": "*",
        "$where": where_clause,
        "$limit": 50000
    })
    df = _to_df(rows)
    # best-effort typing
    for col in ["imposed_date", "collection_ended_date", "dpna_start_date", "dpna_end_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ["civil_money_penalty_amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def fetch_deficiencies(ccns: List[str], since_iso: Optional[str]) -> pd.DataFrame:
    where_clause = f"federal_provider_number in ({','.join([repr(x) for x in ccns])})"
    if since_iso:
        where_clause += f" AND inspection_date >= '{since_iso}'"
    rows = _socrata_get(DATASET_DEFICIENCIES, {
        "$select": "*",
        "$where": where_clause,
        "$limit": 50000
    })
    df = _to_df(rows)
    if "inspection_date" in df.columns:
        df["inspection_date"] = pd.to_datetime(df["inspection_date"], errors="coerce")
    return df

def fetch_provider_info(ccns: List[str]) -> pd.DataFrame:
    rows = _socrata_get(DATASET_PROVIDER_INFO, {
        "$select": "*",
        "$where": f"federal_provider_number in ({','.join([repr(x) for x in ccns])})",
        "$limit": 50000
    })
    df = _to_df(rows)
    # Parse dates & numerics where common
    if "month_year" in df.columns:
        df["month_year"] = pd.to_datetime(df["month_year"], errors="coerce")
    numeric_candidates = [
        "overall_rating","staffing_rating",
        "total_nurse_staffing_hours_per_resident_per_day",
        "rn_staffing_hours_per_resident_per_day",
        "weekend_total_nurse_staff_hours_per_resident_per_day",
        "rn_turnover","total_nurse_staff_turnover","administrator_turnover"
    ]
    for c in numeric_candidates:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # last inspection fields vary; keep as-is
    return df

def fetch_snf_qrp(ccns: List[str]) -> pd.DataFrame:
    # QRP measure column names vary; this fetches all and we subset later
    rows = _socrata_get(DATASET_SNF_QRP, {
        "$select": "*",
        "$where": f"federal_provider_number in ({','.join([repr(x) for x in ccns])})",
        "$limit": 50000
    })
    df = _to_df(rows)
    # parse numerics for common measures if present
    for c in df.columns:
        if c.endswith("_rate") or c.endswith("_ratio") or c.endswith("_score") or c.endswith("_percent"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # date-ish fields
    for c in ["as_of_date", "reporting_period_start_date", "reporting_period_end_date"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df

def fetch_snf_vbp(ccns: List[str]) -> pd.DataFrame:
    rows = _socrata_get(DATASET_SNF_VBP, {
        "$select": "*",
        "$where": f"federal_provider_number in ({','.join([repr(x) for x in ccns])})",
        "$limit": 50000
    })
    df = _to_df(rows)
    for c in ["incentive_payment_multiplier","total_performance_score","achievement_score","improvement_score","rank"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# -----------------------------
# Snapshot helpers
# -----------------------------
def today_str() -> str:
    return dt.date.today().isoformat()

def latest_snapshot_dir(exclude_today: bool = False) -> Optional[Path]:
    dirs = sorted([Path(p) for p in SNAP_DIR.glob("*") if Path(p).is_dir()])
    if not dirs:
        return None
    if exclude_today:
        dirs = [d for d in dirs if d.name != today_str()]
    return dirs[-1] if dirs else None

def save_snapshot(frames: Dict[str, pd.DataFrame]) -> Path:
    d = SNAP_DIR / today_str()
    d.mkdir(parents=True, exist_ok=True)
    for name, df in frames.items():
        fp = d / f"{name}.parquet"
        if df is None or df.empty:
            # write an empty file to lock schema date
            pd.DataFrame().to_parquet(fp, index=False)
        else:
            df.to_parquet(fp, index=False)
    return d

def load_snapshot(path: Path) -> Dict[str, pd.DataFrame]:
    out = {}
    for pq in path.glob("*.parquet"):
        try:
            out[pq.stem] = pd.read_parquet(pq)
        except Exception:
            out[pq.stem] = pd.DataFrame()
    return out

# -----------------------------
# Diff logic → "what's new" events
# -----------------------------
def _mk_event(kind: str, severity: str, text: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    return {
        "type": kind,         # e.g., "penalty", "deficiency", "staffing", "star", "qrp", "vbp"
        "severity": severity, # "info" | "warn" | "high"
        "message": text,
        "data": data or {}
    }

def diff_penalties(prev: pd.DataFrame, curr: pd.DataFrame, ccn: str) -> List[Dict[str, Any]]:
    ev = []
    p_prev = prev[prev.get("ccn","").astype(str) == ccn] if not prev.empty else pd.DataFrame()
    p_curr = curr[curr.get("ccn","").astype(str) == ccn] if not curr.empty else pd.DataFrame()
    if p_curr.empty and p_prev.empty:
        return ev

    # Identify NEW penalties by (imposed_date, CMP amount, dpna_start_date)
    key_cols = ["imposed_date","civil_money_penalty_amount","dpna_start_date","dpna_end_date"]
    def _key(df):
        for col in key_cols:
            if col not in df.columns:
                df[col] = pd.NaT if "date" in col else pd.NA
        return df[key_cols].astype(str).agg("|".join, axis=1)

    prev_keys = set(_key(p_prev)) if not p_prev.empty else set()
    for _, row in p_curr.iterrows():
        k = "|".join([
            str(row.get("imposed_date","")),
            str(row.get("civil_money_penalty_amount","")),
            str(row.get("dpna_start_date","")),
            str(row.get("dpna_end_date","")),
        ])
        if k not in prev_keys:
            amt = row.get("civil_money_penalty_amount", None)
            dpna_start = row.get("dpna_start_date", None)
            dpna_end = row.get("dpna_end_date", None)
            if pd.notna(amt) and float(amt) > 0:
                ev.append(_mk_event("penalty", "high",
                                    f"New CMP imposed: ${float(amt):,.0f} (imposed {str(row.get('imposed_date'))[:10]})",
                                    {"amount": amt}))
            if pd.notna(dpna_start) and (pd.isna(dpna_end) or str(dpna_end) == "" or pd.to_datetime(dpna_end, errors="coerce") > dt.datetime.now()):
                ev.append(_mk_event("penalty", "high",
                                    f"DPNA active or newly started ({str(dpna_start)[:10]} → {str(dpna_end)[:10] if pd.notna(dpna_end) else 'ongoing'})",
                                    {"dpna_start": str(dpna_start), "dpna_end": str(dpna_end)}))
    return ev

def diff_deficiencies(prev: pd.DataFrame, curr: pd.DataFrame, ccn: str) -> List[Dict[str, Any]]:
    ev = []
    d_prev = prev[prev.get("ccn","").astype(str) == ccn] if not prev.empty else pd.DataFrame()
    d_curr = curr[curr.get("ccn","").astype(str) == ccn] if not curr.empty else pd.DataFrame()
    if d_curr.empty:
        return ev
    # New rows since last snapshot (by tag + inspection_date)
    def _key(df):
        cols = ["deficiency_tag","inspection_date","scope_and_severity"]
        for c in cols:
            if c not in df.columns:
                df[c] = pd.NA
        return df[cols].astype(str).agg("|".join, axis=1)

    prev_keys = set(_key(d_prev)) if not d_prev.empty else set()
    for _, r in d_curr.iterrows():
        k = "|".join([str(r.get("deficiency_tag","")), str(r.get("inspection_date","")), str(r.get("scope_and_severity",""))])
        if k not in prev_keys:
            sev = str(r.get("scope_and_severity","")).upper()
            tag = str(r.get("deficiency_tag",""))
            date = str(r.get("inspection_date",""))[:10]
            msg = f"New deficiency {tag} ({sev}) on {date}"
            ev.append(_mk_event("deficiency", "high" if sev in {"J","K","L"} else "warn", msg, {
                "tag": tag, "scope_severity": sev, "date": date
            }))
    return ev

def diff_provider_info(prev: pd.DataFrame, curr: pd.DataFrame, ccn: str) -> List[Dict[str, Any]]:
    ev = []
    p_prev = prev[prev.get("ccn","").astype(str) == ccn] if not prev.empty else pd.DataFrame()
    p_curr = curr[curr.get("ccn","").astype(str) == ccn] if not curr.empty else pd.DataFrame()
    if p_curr.empty:
        return ev

    # Take latest month_year for each snapshot
    def latest_row(df: pd.DataFrame) -> Optional[pd.Series]:
        if df.empty:
            return None
        if "month_year" in df.columns:
            df = df.sort_values("month_year")
            return df.iloc[-1]
        return df.iloc[-1]

    r_prev = latest_row(p_prev)
    r_curr = latest_row(p_curr)

    def _get(s: Optional[pd.Series], col: str, default=None):
        if s is None:
            return default
        return s.get(col, default)

    # Star changes
    for col, label in [
        ("overall_rating","Overall star"),
        ("staffing_rating","Staffing star"),
    ]:
        old = _get(r_prev, col)
        new = _get(r_curr, col)
        if pd.notna(new) and (pd.isna(old) or new != old):
            delta = (None if pd.isna(old) else new - old)
            msg = f"{label} {'changed' if pd.notna(delta) else 'reported'}: {old} → {new}"
            sev = "warn" if (label == "Overall star" and pd.notna(delta) and delta < 0) else "info"
            ev.append(_mk_event("star", sev, msg, {"from": old, "to": new}))

    # Staffing signal thresholds
    def pct_change(a, b):
        try:
            return (b - a) / a if a not in (None, 0, pd.NA, pd.NaT) and pd.notna(a) else math.inf
        except Exception:
            return math.inf

    # HPRD drop ≥10%
    hprd_prev = _get(r_prev, "total_nurse_staffing_hours_per_resident_per_day")
    hprd_curr = _get(r_curr, "total_nurse_staffing_hours_per_resident_per_day")
    if pd.notna(hprd_prev) and pd.notna(hprd_curr):
        chg = pct_change(hprd_prev, hprd_curr)
        if chg <= -0.10:
            ev.append(_mk_event("staffing", "warn",
                                f"Total nurse HPRD fell ≥10%: {hprd_prev:.2f} → {hprd_curr:.2f}",
                                {"from": hprd_prev, "to": hprd_curr}))

    # Weekend staffing dip vs weekday proxy (simple heuristic if present)
    wknd_prev = _get(r_prev, "weekend_total_nurse_staff_hours_per_resident_per_day")
    wknd_curr = _get(r_curr, "weekend_total_nurse_staff_hours_per_resident_per_day")
    if pd.notna(wknd_prev) and pd.notna(wknd_curr) and pd.notna(hprd_curr):
        if wknd_curr < 0.8 * hprd_curr:
            ev.append(_mk_event("staffing", "info",
                                f"Weekend staffing is low vs weekday baseline: wknd {wknd_curr:.2f} vs overall {hprd_curr:.2f}",
                                {"wknd": wknd_curr, "overall": hprd_curr}))

    # Turnover increases ≥5 pp
    for col, label in [("rn_turnover","RN turnover"), ("total_nurse_staff_turnover","Total nurse turnover"), ("administrator_turnover","Administrator turnover")]:
        old = _get(r_prev, col)
        new = _get(r_curr, col)
        if pd.notna(old) and pd.notna(new) and (new - old) >= 0.05:
            ev.append(_mk_event("staffing", "warn",
                                f"{label} increased: {old:.2%} → {new:.2%}",
                                {"from": float(old), "to": float(new)}))
    return ev

def diff_snf_qrp(prev: pd.DataFrame, curr: pd.DataFrame, ccn: str) -> List[Dict[str, Any]]:
    ev = []
    q_prev = prev[prev.get("ccn","").astype(str) == ccn] if not prev.empty else pd.DataFrame()
    q_curr = curr[curr.get("ccn","").astype(str) == ccn] if not curr.empty else pd.DataFrame()
    if q_curr.empty:
        return ev

    # Keep the latest row if there's an as_of_date or reporting_end
    def pick_latest(df):
        for c in ["as_of_date","reporting_period_end_date"]:
            if c in df.columns:
                return df.sort_values(c).iloc[-1]
        return df.iloc[-1]

    r_prev = pick_latest(q_prev) if not q_prev.empty else None
    r_curr = pick_latest(q_curr)

    # Common measure name guesses (schema varies)
    MEAS = [
        ("discharge_to_community_rate", "Discharge to Community (higher is better)", +1, 0.02),
        ("potentially_preventable_30_day_post_discharge_readmission_rate", "Potentially Preventable Readmissions (lower is better)", -1, 0.02),
        ("mspb_pac_snf_ratio", "MSPB-PAC (lower is better)", -1, 0.02),
        ("hai_hospitalization_rate", "HAI requiring hospitalization (lower is better)", -1, 0.01),
    ]

    def safe_num(row, col):
        if row is None:
            return None
        v = row.get(col, None)
        try:
            return float(v)
        except Exception:
            return None

    for col, label, direction, thresh in MEAS:
        if col in q_curr.columns:
            old = safe_num(r_prev, col) if r_prev is not None else None
            new = safe_num(r_curr, col)
            if new is not None and (old is None or abs(new - old) >= thresh):
                arrow = "↑" if (new > (old if old is not None else new)) else "↓"
                worse = (direction == +1 and new < (old or new)) or (direction == -1 and new > (old or new))
                sev = "warn" if old is not None and worse else "info"
                msg = f"{label} changed: {old if old is not None else 'n/a'} → {new} ({arrow})"
                ev.append(_mk_event("qrp", sev, msg, {"measure": col, "from": old, "to": new}))
    return ev

def diff_snf_vbp(prev: pd.DataFrame, curr: pd.DataFrame, ccn: str) -> List[Dict[str, Any]]:
    ev = []
    v_prev = prev[prev.get("ccn","").astype(str) == ccn] if not prev.empty else pd.DataFrame()
    v_curr = curr[curr.get("ccn","").astype(str) == ccn] if not curr.empty else pd.DataFrame()
    if v_curr.empty:
        return ev

    # If multiple fiscal years exist, keep the latest multiplier row (no standard date → use rank or presence)
    def pick_latest(df):
        if "fiscal_year" in df.columns:
            try:
                return df.sort_values("fiscal_year").iloc[-1]
            except Exception:
                pass
        return df.iloc[-1]

    r_prev = pick_latest(v_prev) if not v_prev.empty else None
    r_curr = pick_latest(v_curr)

    old = float(r_prev.get("incentive_payment_multiplier")) if (r_prev is not None and pd.notna(r_prev.get("incentive_payment_multiplier"))) else None
    new = float(r_curr.get("incentive_payment_multiplier")) if pd.notna(r_curr.get("incentive_payment_multiplier")) else None

    if new is not None and (old is None or abs(new - old) >= 0.005):
        sev = "warn" if (old is not None and new < old) else "info"
        msg = f"SNF VBP incentive multiplier: {old if old is not None else 'n/a'} → {new:.3f}"
        ev.append(_mk_event("vbp", sev, msg, {"from": old, "to": new}))
    return ev

# -----------------------------
# Orchestrate: pull → snapshot → diff → changelog
# -----------------------------
def build_changelogs(ccns: List[str], days_back: int = 60) -> Dict[str, Dict[str, Any]]:
    since = (dt.date.today() - dt.timedelta(days=days_back)).isoformat()

    # Pull current
    penalties = fetch_penalties(ccns, since_iso=since)
    deficiencies = fetch_deficiencies(ccns, since_iso=since)
    provider = fetch_provider_info(ccns)
    qrp = fetch_snf_qrp(ccns)
    vbp = fetch_snf_vbp(ccns)

    # Save current snapshot
    snap_cur = {
        "penalties": penalties,
        "deficiencies": deficiencies,
        "provider_info": provider,
        "snf_qrp": qrp,
        "snf_vbp": vbp
    }
    cur_dir = save_snapshot(snap_cur)

    # Load previous snapshot (most recent before today)
    prev_dir = latest_snapshot_dir(exclude_today=True)
    prev = load_snapshot(prev_dir) if prev_dir else {"penalties": pd.DataFrame(), "deficiencies": pd.DataFrame(),
                                                     "provider_info": pd.DataFrame(), "snf_qrp": pd.DataFrame(),
                                                     "snf_vbp": pd.DataFrame()}

    # Build changelogs
    results: Dict[str, Dict[str, Any]] = {}
    for ccn in ccns:
        events = []
        events += diff_penalties(prev.get("penalties", pd.DataFrame()), penalties, ccn)
        events += diff_deficiencies(prev.get("deficiencies", pd.DataFrame()), deficiencies, ccn)
        events += diff_provider_info(prev.get("provider_info", pd.DataFrame()), provider, ccn)
        events += diff_snf_qrp(prev.get("snf_qrp", pd.DataFrame()), qrp, ccn)
        events += diff_snf_vbp(prev.get("snf_vbp", pd.DataFrame()), vbp, ccn)

        # Sort by perceived severity (high → warn → info)
        sev_rank = {"high": 0, "warn": 1, "info": 2}
        events.sort(key=lambda e: sev_rank.get(e["severity"], 9))

        # Facility header bits (best-effort from Provider Info latest)
        p = provider[provider.get("ccn","").astype(str) == ccn]
        facility_name = None
        city = state = None
        if not p.empty:
            # pick latest row by month_year if present
            if "month_year" in p.columns:
                p = p.sort_values("month_year").iloc[-1]
            else:
                p = p.iloc[-1]
            facility_name = p.get("provider_name", None)
            # address fields vary by release; try a few
            city = p.get("city", p.get("provider_city", None))
            state = p.get("state", p.get("provider_state", None))
        header = {"ccn": ccn, "provider_name": facility_name, "city": city, "state": state}

        results[ccn] = {"header": header, "events": events}

    # Write per-CCN JSON
    for ccn, payload in results.items():
        out_fp = OUT_DIR / f"{ccn}.json"
        with open(out_fp, "w") as f:
            json.dump(payload, f, indent=2)
    return results

# -----------------------------
# CLI
# -----------------------------
def main():
    ap = argparse.ArgumentParser(description="CMS Post-Acute 'What's New' changelog generator")
    ap.add_argument("--ccn", nargs="+", required=True, help="List of CCNs (e.g., 455682 675791 676336)")
    ap.add_argument("--days", type=int, default=60, help="Look-back window for penalties/deficiencies (default 60)")
    args = ap.parse_args()

    # Normalize CCNs to 6 chars
    ccns = [str(x).zfill(6) for x in args.ccn]
    results = build_changelogs(ccns, days_back=args.days)

    print("\n=== ChangeLog Summary ===")
    for ccn, payload in results.items():
        hdr = payload["header"]
        print(f"\n{hdr.get('provider_name') or 'Facility'} (CCN {ccn}) – {hdr.get('city') or ''}, {hdr.get('state') or ''}")
        if not payload["events"]:
            print("  • No notable changes in the selected window.")
        for e in payload["events"]:
            print(f"  • [{e['severity'].upper()}] {e['message']}")

if __name__ == "__main__":
    main()
