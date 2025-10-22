import io, sys, json, gzip, zipfile, requests, pandas as pd, datetime as dt
from dateutil import tz

CCNS = ["455682", "675791", "676336"]  # <- your facilities (6-digit strings)

# -------------------------------
# 1) Find + download latest PBJ Daily Nurse Staffing (CSV) via data.json
# -------------------------------
def get_latest_pbj_download_url():
    data_json = requests.get("https://data.cms.gov/data.json", timeout=60).json()
    for ds in data_json["dataset"]:
        if ds.get("title","").strip().lower() == "payroll based journal daily nurse staffing":
            # In 'distribution', the first item usually has description 'latest'
            for dist in ds.get("distribution", []):
                # prefer CSV (downloadURL) for simple pandas ingest
                if dist.get("description","").lower() == "latest" and dist.get("mediaType","").startswith(("text/csv","application/zip")):
                    # CSV usually exposed via 'downloadURL'; if missing, fall back to accessURL for the API
                    return dist.get("downloadURL") or dist.get("accessURL")
    raise RuntimeError("PBJ Daily Nurse Staffing 'latest' distribution not found")

pbj_url = get_latest_pbj_download_url()
print("PBJ latest download:", pbj_url)

# -------------------------------
# 2) Load + normalize PBJ daily
#    (The file can be CSV or ZIPped CSV; columns vary slightly; we handle common names)
# -------------------------------
def read_csv_maybe_zip(url):
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()
    content = resp.content
    # If it's a ZIP, read the first CSV inside
    if url.lower().endswith(".zip") or resp.headers.get("Content-Type","").startswith("application/zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            # pick first .csv
            for name in zf.namelist():
                if name.lower().endswith(".csv"):
                    with zf.open(name) as f:
                        return pd.read_csv(f, dtype=str, low_memory=False)
        raise RuntimeError("ZIP has no CSV")
    # else assume CSV
    return pd.read_csv(io.BytesIO(content), dtype=str, low_memory=False)

pbj = read_csv_maybe_zip(pbj_url)

# --- Map likely column names to a standard set ---
def pick_col(df, candidates):
    for c in candidates:
        if c in df.columns: return c
    return None

COL_CCN   = pick_col(pbj, ["CMS_Certification_Number","ccn","federal_provider_number","provider_number","ProviderId"])
COL_DATE  = pick_col(pbj, ["Work_Date","work_date","date","Date"])
COL_RN    = pick_col(pbj, ["Hrs_RN","hrs_rn","HrsRN","RN_Hours"])
COL_LPN   = pick_col(pbj, ["Hrs_LPN","hrs_lpn","HrsLPN","LPN_Hours"])
COL_CNA   = pick_col(pbj, ["Hrs_CNA","hrs_cna","HrsCNA","CNA_Hours"])
COL_TOT   = pick_col(pbj, ["Hrs_Total_Nurse_Staff","hrs_total_nurse_staff","Total_Nurse_Hours"])
COL_CENS  = pick_col(pbj, ["Resident_Census","resident_census","Census","resident_count"])

need = [COL_CCN, COL_DATE, COL_CENS]
if not all(need):
    missing = [n for n,v in zip(["CCN","DATE","CENSUS"], need) if v is None]
    raise RuntimeError(f"PBJ: missing required columns {missing}")

# Compute total nurse hours if not pre-aggregated
if COL_TOT is None:
    if not all([COL_RN, COL_LPN, COL_CNA]):
        raise RuntimeError("PBJ: need RN/LPN/CNA hours or a total hours column")
    pbj["total_hours"] = (
        pd.to_numeric(pbj[COL_RN], errors="coerce").fillna(0) +
        pd.to_numeric(pbj[COL_LPN], errors="coerce").fillna(0) +
        pd.to_numeric(pbj[COL_CNA], errors="coerce").fillna(0)
    )
else:
    pbj["total_hours"] = pd.to_numeric(pbj[COL_TOT], errors="coerce")

pbj["ccn"]  = pbj[COL_CCN].astype(str).str.zfill(6)
pbj["date"] = pd.to_datetime(pbj[COL_DATE], errors="coerce")
pbj["census"] = pd.to_numeric(pbj[COL_CENS], errors="coerce")
pbj = pbj[pbj["ccn"].isin([c.zfill(6) for c in CCNS])].dropna(subset=["date","census"])

# HPRD = total hours / resident count
pbj["hprd"] = (pbj["total_hours"] / pbj["census"]).replace([pd.NA, pd.NaT], pd.NA)

# -------------------------------
# 3) Build last-30 vs prior-30 windows inside the most recent dates available
# -------------------------------
max_date = pbj["date"].max()
last30_start = max_date - pd.Timedelta(days=29)
prev30_start = last30_start - pd.Timedelta(days=30)
prev30_end   = last30_start - pd.Timedelta(days=1)

pbj_last30 = pbj[(pbj["date"] >= last30_start) & (pbj["date"] <= max_date)]
pbj_prev30 = pbj[(pbj["date"] >= prev30_start) & (pbj["date"] <= prev30_end)]

# Weekend flag
pbj_last30["is_weekend"] = pbj_last30["date"].dt.dayofweek.isin([5,6])

def summarize_hprd(df):
    if df.empty: return pd.Series({"hprd_mean": pd.NA})
    return pd.Series({"hprd_mean": df["hprd"].mean(skipna=True)})

def staffing_summary(pbj_last30, pbj_prev30):
    # facility-level summaries
    last30_all = pbj_last30.groupby("ccn").apply(summarize_hprd).rename(columns={"hprd_mean":"hprd_last30"})
    prev30_all = pbj_prev30.groupby("ccn").apply(summarize_hprd).rename(columns={"hprd_mean":"hprd_prev30"})
    # weekend vs weekday (last 30)
    last30_weekend = pbj_last30[pbj_last30["is_weekend"]].groupby("ccn")["hprd"].mean().rename("hprd_weekend")
    last30_weekday = pbj_last30[~pbj_last30["is_weekend"]].groupby("ccn")["hprd"].mean().rename("hprd_weekday")

    out = last30_all.join(prev30_all, how="left").join(last30_weekend, how="left").join(last30_weekday, how="left")
    # pct change last30 vs prev30
    out["hprd_pct_change"] = (out["hprd_last30"] - out["hprd_prev30"]) / out["hprd_prev30"]
    # weekend ratio vs weekday
    out["weekend_ratio"] = out["hprd_weekend"] / out["hprd_weekday"]
    return out.reset_index()

staffing = staffing_summary(pbj_last30, pbj_prev30)

# -------------------------------
# 4) Pull turnover from Provider Information (Socrata / dataset id 4pq5-n9py)
# -------------------------------
def socrata_get(dataset_id, params):
    base = f"https://data.cms.gov/resource/{dataset_id}.json"
    r = requests.get(base, params=params, timeout=60)
    r.raise_for_status()
    return pd.DataFrame(r.json())

# Select needed fields (column names from the NH Data Dictionary)
fields = [
    "federal_provider_number","provider_name","city","state","month_year",
    "rn_turnover","total_nurse_staff_turnover","administrator_turnover",
    "weekend_total_nurse_staff_hours_per_resident_per_day"
]
q = {
    "$select": ",".join(fields),
    "$where": f"federal_provider_number in ({','.join([repr(c) for c in CCNS])})",
    "$limit": 50000
}
prov = socrata_get("4pq5-n9py", q)
if not prov.empty:
    prov["ccn"] = prov["federal_provider_number"].astype(str).str.zfill(6)
    prov["month_year"] = pd.to_datetime(prov["month_year"], errors="coerce")
    for c in ["rn_turnover","total_nurse_staff_turnover","administrator_turnover",
              "weekend_total_nurse_staff_hours_per_resident_per_day"]:
        if c in prov.columns:
            prov[c] = pd.to_numeric(prov[c], errors="coerce")

    # Latest vs prior month for turnover deltas
    prov_sorted = prov.sort_values(["ccn","month_year"])
    latest = prov_sorted.groupby("ccn").tail(1).set_index("ccn")
    prior  = prov_sorted.groupby("ccn").nth(-2) if prov_sorted.groupby("ccn").size().min() >= 2 else pd.DataFrame()

    if not prior.empty:
        for col in ["rn_turnover","total_nurse_staff_turnover","administrator_turnover"]:
            latest[f"{col}_delta"] = latest[col] - prior[col]

    turnover = latest.reset_index()[["ccn","rn_turnover","total_nurse_staff_turnover","administrator_turnover",
                                     "rn_turnover_delta","total_nurse_staff_turnover_delta","administrator_turnover_delta"]]
else:
    turnover = pd.DataFrame(columns=["ccn"])

# -------------------------------
# 5) Merge + flag your three signals
# -------------------------------
out = staffing.merge(turnover, on="ccn", how="left")

def flag(row):
    notes = []
    # A) HPRD drop ≥ 10%
    if pd.notna(row.get("hprd_pct_change", pd.NA)) and row["hprd_pct_change"] <= -0.10:
        notes.append(f"HPRD fell ≥10%: {row['hprd_prev30']:.2f}→{row['hprd_last30']:.2f}")
    # B) Weekend staffing < 80% of weekday
    if pd.notna(row.get("weekend_ratio", pd.NA)) and row["weekend_ratio"] < 0.80:
        notes.append(f"Weekend staffing low: {row['weekend_ratio']:.0%} of weekday")
    # C) Turnover increases ≥5 percentage points (month over month)
    for col,label in [("rn_turnover_delta","RN"),("total_nurse_staff_turnover_delta","Nurse"),("administrator_turnover_delta","Admin")]:
        val = row.get(col, None)
        if val is not None and pd.notna(val) and val >= 0.05:
            notes.append(f"{label} turnover +{val*100:.0f} pp m/m")
    return "; ".join(notes) if notes else ""

out["staffing_alerts"] = out.apply(flag, axis=1)

print("\n=== Staffing stability signals (last 30 days) ===")
for _, r in out.iterrows():
    print(f"{r['ccn']}: {r.get('staffing_alerts','') or 'No flags'}")
