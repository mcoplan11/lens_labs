#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

- Reads Medicare Physician & Other Supplier PUF CSV.
- Produces:
  1) Stacked bar: share of E/M service levels by specialty (top N specialties)
  2) Scatter: avg complexity vs avg Medicare allowed amount (bubble = total services)
  3) State choropleth: avg complexity by state
  4) RUCA (urban/rural) comparison for top specialties
  5) Provider outlier detection (save CSV of top outliers)
- Optional: merges a provider-level HCC file (provider_hcc_scores.csv)
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Optional visualization lib for choropleth
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# --- User config ---
CSV_FILE = "/Users/mitchell_coplan/Downloads/Medicare Physician & Other Practitioners - by Provider and Service/2023/MUP_PHY_R25_P05_V20_D23_Prov_Svc.csv"
OUTPUT_DIR = Path("outputs")
TOP_N_SPECIALTIES = 8
SAVE_PNG = True
SAVE_HTML = True

# --- Helpers ---
def pick_col(df, candidates):
    """Pick the first matching column from a list of candidates (case-insensitive)."""
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())
    col_map = {norm(c): c for c in df.columns}
    for cand in candidates:
        n = norm(cand)
        if n in col_map:
            return col_map[n]
    raise KeyError(f"None of the candidate columns found: {candidates}. Found columns: {list(df.columns)[:20]}")

def weighted_avg(series, weights):
    s = series * weights
    return s.sum() / weights.sum() if weights.sum() > 0 else np.nan


# --- E/M complexity mapping ---
EM_CODES = {
    "99211": 1, "99212": 2, "99213": 3, "99214": 4, "99215": 5,
    "99201": 1, "99202": 2, "99203": 3, "99204": 4, "99205": 5,
    "99221": 2, "99222": 3, "99223": 4,
    "99231": 2, "99232": 3, "99233": 4,
    "99238": 4, "99239": 5,
}

# Ensure output dir exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Load CSV ---
print("Loading CSV:", CSV_FILE)
df = pd.read_csv(CSV_FILE, low_memory=False)
print("Initial shape:", df.shape)

# --- Detect columns ---
hcpcs_col = pick_col(df, ["HCPCS_Cd"])
specialty_col = pick_col(df, ["Rndrng_Prvdr_Type", "Provider_Type"])
npi_col = pick_col(df, ["Rndrng_NPI", "NPI"])
tot_srvs_col = pick_col(df, ["Tot_Srvcs"])
tot_benes_col = pick_col(df, ["Tot_Benes"])
avg_allowed_col = pick_col(df, ["Avg_Mdcr_Alowd_Amt"])
state_col = pick_col(df, ["Rndrng_Prvdr_State_Abrvtn", "state"])

ruca_col = None
for cand in ["Rndrng_Prvdr_RUCA_Desc", "ruca_desc"]:
    try:
        ruca_col = pick_col(df, [cand])
        break
    except KeyError:
        continue

print("Using columns:", hcpcs_col, specialty_col, tot_srvs_col, tot_benes_col, avg_allowed_col, state_col, "RUCA:", ruca_col)

# --- Clean numeric columns ---
df[tot_srvs_col] = pd.to_numeric(df[tot_srvs_col], errors="coerce").fillna(0)
df[tot_benes_col] = pd.to_numeric(df[tot_benes_col], errors="coerce").fillna(0)
df[avg_allowed_col] = pd.to_numeric(df[avg_allowed_col], errors="coerce").fillna(np.nan)

# --- Normalize and filter ---
df["_hcpcs"] = df[hcpcs_col].astype(str).str.strip().str.replace(r"\.0+$", "", regex=True)
df["specialty"] = df[specialty_col].astype(str).str.strip()
df["_state"] = df[state_col].astype(str).str.strip().str.upper()
df["_complexity"] = df["_hcpcs"].map(EM_CODES)
df_em = df[df["_complexity"].notnull()].copy()
print("Rows matching mapped E/M codes:", len(df_em))

# --- Aggregated specialty-level metrics ---
agg = df_em.groupby("specialty", as_index=False).agg(
    avg_complexity=pd.NamedAgg(column="_complexity", aggfunc=lambda x: weighted_avg(x, df_em.loc[x.index, tot_srvs_col])),
    total_services=pd.NamedAgg(column=tot_srvs_col, aggfunc="sum"),
    total_benes=pd.NamedAgg(column=tot_benes_col, aggfunc="sum"),
    avg_allowed=pd.NamedAgg(column=avg_allowed_col, aggfunc=lambda x: weighted_avg(x.fillna(0), df_em.loc[x.index, tot_srvs_col]))
)

# Top specialties
top_specialties = agg.sort_values("total_services", ascending=False).head(TOP_N_SPECIALTIES)["specialty"].tolist()
print("Top specialties:", top_specialties)

# # --- 1) Stacked bar: E/M distribution ---
# dist = df_em[df_em["specialty"].isin(top_specialties)].groupby(["specialty", "_hcpcs"])[tot_srvs_col].sum().reset_index()
# pivot = dist.pivot(index="specialty", columns="_hcpcs", values=tot_srvs_col).fillna(0)
# pivot_pct = pivot.div(pivot.sum(axis=1), axis=0).loc[top_specialties]

# plt.figure(figsize=(10,6))
# bottom = np.zeros(len(pivot_pct))
# for level in pivot_pct.columns:
#     vals = pivot_pct[level].values
#     plt.barh(range(len(vals)), vals, left=bottom, label=level)
#     bottom += vals
# plt.yticks(range(len(top_specialties)), top_specialties)
# plt.xlabel("Share of E/M services")
# plt.title(f"Distribution of E/M Levels across Top {len(top_specialties)} Specialties")
# plt.legend(title="HCPCS Level", bbox_to_anchor=(1.02,1), loc="upper left")
# plt.gca().invert_yaxis()
# plt.tight_layout()
# if SAVE_PNG:
#     out = OUTPUT_DIR / "em_distribution_by_specialty.png"
#     plt.savefig(out, dpi=300)
#     print("Saved:", out)

# # --- 2) Scatter: avg complexity vs avg allowed ---
# scatter_df = agg.copy()
# scatter_df["size"] = (scatter_df["total_services"] / scatter_df["total_services"].max()) * 300
# plt.figure(figsize=(10,6))
# plt.scatter(scatter_df["avg_complexity"], scatter_df["avg_allowed"], s=scatter_df["size"], alpha=0.7)
# for _, r in scatter_df.sort_values("total_services", ascending=False).head(12).iterrows():
#     plt.annotate(r["specialty"], (r["avg_complexity"], r["avg_allowed"]), xytext=(6,-4), textcoords="offset points")
# plt.xlabel("Average Complexity Score (weighted)")
# plt.ylabel("Average Medicare Allowed Amount (weighted)")
# plt.title("Specialty: Complexity vs Medicare Allowed Amount")
# plt.grid(axis="y", alpha=0.2)
# plt.tight_layout()
# if SAVE_PNG:
#     out = OUTPUT_DIR / "complexity_vs_allowed_by_specialty.png"
#     plt.savefig(out, dpi=300)
#     print("Saved:", out)

# # --- 3) State choropleth ---
# state_agg = df_em.groupby("_state", as_index=False).apply(
#     lambda g: pd.Series({
#         "avg_complexity": weighted_avg(g["_complexity"], g[tot_srvs_col]),
#         "total_services": g[tot_srvs_col].sum()
#     })
# )
# if PLOTLY_AVAILABLE:
#     fig = px.choropleth(
#         state_agg,
#         locations="_state",
#         locationmode="USA-states",
#         color="avg_complexity",
#         scope="usa",
#         hover_data=["total_services", "avg_complexity"],
#         title="Average E/M Complexity by State"
#     )
#     if SAVE_HTML:
#         html_out = OUTPUT_DIR / "complexity_by_state.html"
#         fig.write_html(str(html_out))
#         print("Saved:", html_out)
#     if SAVE_PNG:
#         png_out = OUTPUT_DIR / "complexity_by_state.png"
#         fig.write_image(str(png_out), scale=2)
#         print("Saved:", png_out)
# else:
#     print("Plotly not installed — skipping choropleth.")

# # --- 4) RUCA comparison ---
# if ruca_col:
#     ruca_df = df_em[df_em["specialty"].isin(top_specialties)].copy()
#     ruca_df["_ruca"] = df[ruca_col].astype(str).fillna("Unknown")
#     ruca_agg = ruca_df.groupby(["specialty", "_ruca"]).apply(
#         lambda g: weighted_avg(g["_complexity"], g[tot_srvs_col])
#     ).reset_index(name="avg_complexity")
#     ruca_pivot = ruca_agg.pivot(index="specialty", columns="_ruca", values="avg_complexity").reindex(top_specialties)
#     ruca_pivot.plot(kind="barh", figsize=(12,7))
#     plt.xlabel("Avg Complexity")
#     plt.title("Avg E/M Complexity by RUCA (Top Specialties)")
#     plt.tight_layout()
#     if SAVE_PNG:
#         out = OUTPUT_DIR / "complexity_by_ruca_top_specialties.png"
#         plt.savefig(out, dpi=300)
#         print("Saved:", out)
# else:
#     print("RUCA column not found — skipping RUCA analysis.")

# # --- 5) Provider outlier detection ---
# prov = df_em.groupby([npi_col, "specialty"], as_index=False).apply(
#     lambda g: pd.Series({
#         "avg_complexity": weighted_avg(g["_complexity"], g[tot_srvs_col]),
#         "total_services": g[tot_srvs_col].sum(),
#         "total_benes": g[tot_benes_col].sum()
#     })
# )
# prov["z"] = prov.groupby("specialty")["avg_complexity"].transform(lambda x: (x - x.mean()) / x.std(ddof=0))
# outliers = prov[(prov["z"] > 2.5) & (prov["total_services"] >= 50)].sort_values("z", ascending=False)
# out_csv = OUTPUT_DIR / "provider_complexity_outliers.csv"
# outliers.to_csv(out_csv, index=False)
# print(f"Saved provider outliers ({len(outliers)}) to:", out_csv)


# ----------------------------
# Provider overlap analysis
# ----------------------------
import seaborn as sns
from matplotlib import cm


# ----------------------------
# Provider-level aggregation (weighted by services)
# ----------------------------
prov = (
    df_em.groupby([npi_col, "specialty"], as_index=False)
    .apply(lambda g: pd.Series({
        "avg_complexity": (g["_complexity"] * g[tot_srvs_col]).sum() / g[tot_srvs_col].sum()
                          if g[tot_srvs_col].sum() > 0 else np.nan,
        "total_services": g[tot_srvs_col].sum()
    }))
    .reset_index(drop=True)   # no extra level_0 column anymore
)

# Make sure expected columns exist
prov = prov[[npi_col, "specialty", "avg_complexity", "total_services"]]

# sometimes .reset_index() names differ; ensure we have an npi column
if npi_col not in prov.columns:
    # try alternate index name
    prov = prov.rename(columns={prov.columns[0]: npi_col})

# filter out tiny providers to reduce noise (optional threshold)
MIN_SRVS = 20
prov_filt = prov[prov["total_services"] >= MIN_SRVS].copy()
print("Providers after filtering (>= %d services): %d" % (MIN_SRVS, len(prov_filt)))

# Build list of specialties to compare (top by provider count)
specialty_counts = prov_filt["specialty"].value_counts().sort_values(ascending=False)
TOP_SPEC_CNT = 12
compare_specialties = specialty_counts.head(TOP_SPEC_CNT).index.tolist()
print("Comparing specialties:", compare_specialties)

prov_sub = prov_filt[prov_filt["specialty"].isin(compare_specialties)].copy()

# Precompute medians and percentiles per specialty
spec_stats = prov_sub.groupby("specialty")["avg_complexity"].agg(["median", "mean", lambda x: np.percentile(x.dropna(), 75)])
spec_stats = spec_stats.rename(columns={"<lambda_0>": "p75"})
spec_stats = spec_stats.sort_values("median", ascending=False)
print("Specialty medians:\n", spec_stats["median"].round(3))

# Overlap matrix: % of providers in A above median(B)
overlap = pd.DataFrame(index=compare_specialties, columns=compare_specialties, dtype=float)
for a in compare_specialties:
    a_vals = prov_sub[prov_sub["specialty"] == a]["avg_complexity"].dropna()
    for b in compare_specialties:
        med_b = prov_sub[prov_sub["specialty"] == b]["avg_complexity"].median()
        if np.isnan(med_b) or len(a_vals) == 0:
            overlap.loc[a, b] = np.nan
        else:
            overlap.loc[a, b] = 100.0 * (a_vals > med_b).sum() / len(a_vals)

# Save overlap CSV optionally (commented out)
# overlap.to_csv(OUTPUT_DIR / "specialty_overlap_matrix_pct.csv", index=True)

# Pretty heatmap
plt.figure(figsize=(12,9))
sns.set(style="white")
mask = overlap.isnull()
cmap = sns.diverging_palette(220, 10, as_cmap=True)
ax = sns.heatmap(overlap.astype(float), annot=True, fmt=".1f", cmap="YlOrRd", linewidths=.5, linecolor="white",
                 cbar_kws={'label': '% of A above median(B)'}, vmin=0, vmax=100)
ax.set_title("% of providers in Specialty A with avg complexity > median provider in Specialty B", pad=16)
plt.ylabel("Specialty A (rows)")
plt.xlabel("Specialty B (columns)")
plt.xticks(rotation=45, ha="right")
plt.yticks(rotation=0)
plt.tight_layout()
heat_out = OUTPUT_DIR / "specialty_overlap_heatmap.png"
plt.savefig(heat_out, dpi=300)
print("Saved heatmap:", heat_out)

# Identify and print the most surprising overlaps for story lines:
# e.g., Non-intuitive pairs where a traditionally 'lower' specialty has many providers above medians of higher specialties.
# We'll find pairs where median(B) > median(A) but >20% of A are above median(B).
surprising = []
medians = prov_sub.groupby("specialty")["avg_complexity"].median()
for a in compare_specialties:
    for b in compare_specialties:
        if a == b: continue
        if np.isnan(medians.get(a, np.nan)) or np.isnan(medians.get(b, np.nan)): continue
        if medians[b] > medians[a]:
            pct = overlap.loc[a, b]
            if pd.notna(pct) and pct >= 20:  # threshold to call out
                surprising.append((a, b, medians[a], medians[b], pct))
surprising_sorted = sorted(surprising, key=lambda x: -x[4])
print("\nTop surprising overlaps (A, B, medianA, medianB, % of A > medianB):")
for a,b,ma,mb,pct in surprising_sorted[:10]:
    print(f" - {a} vs {b}: medianA={ma:.2f}, medianB={mb:.2f}, {pct:.1f}% of {a} providers > median({b})")

# ----------------------------
# Violin + swarm plot for LinkedIn figure
# ----------------------------
plt.figure(figsize=(14,8))
order = prov_sub.groupby("specialty")["avg_complexity"].median().sort_values(ascending=False).index
sns.violinplot(data=prov_sub, x="avg_complexity", y="specialty", order=order, cut=0, scale="width")
sns.stripplot(data=prov_sub, x="avg_complexity", y="specialty", order=order, size=3, jitter=True, alpha=0.6, linewidth=0)
# Add vertical median lines for each specialty's median (thin)
for i, spec in enumerate(order):
    med = medians.loc[spec]
    plt.plot([med, med], [i - 0.4, i + 0.4], color="k", linewidth=1)

plt.xlabel("Provider average E/M complexity (weighted)")
plt.ylabel("")
plt.title("Distribution of provider-level avg E/M complexity (top specialties)\nEach dot = a provider. Violin = density. Vertical tick = specialty median.")
plt.tight_layout()
violin_out = OUTPUT_DIR / "provider_complexity_violins.png"
plt.savefig(violin_out, dpi=300)
print("Saved violin plot:", violin_out)

# Create a compact 'callout' image that annotates one or two high-impact facts:
# pick the top 3 surprising_sorted and annotate on violin chart (re-open, save annotated copy)
if len(surprising_sorted) > 0:
    plt.figure(figsize=(14,8))
    sns.violinplot(data=prov_sub, x="avg_complexity", y="specialty", order=order, cut=0, scale="width")
    sns.stripplot(data=prov_sub, x="avg_complexity", y="specialty", order=order, size=3, jitter=True, alpha=0.6, linewidth=0)
    for i, spec in enumerate(order):
        med = medians.loc[spec]
        plt.plot([med, med], [i - 0.4, i + 0.4], color="k", linewidth=1)

    # annotate top 3
    for idx, (a,b,ma,mb,pct) in enumerate(surprising_sorted[:3]):
        y = list(order).index(a)
        x = mb  # place annotation at median of B
        plt.annotate(f"{pct:.0f}% of {a} > median({b})",
                     xy=(x, y), xytext=(x + 0.4, y - 0.25 - idx*0.25),
                     arrowprops=dict(arrowstyle="->", lw=1),
                     fontsize=10, bbox=dict(boxstyle="round,pad=0.3", alpha=0.8))
    plt.title("Provider complexity distributions with top overlap callouts")
    plt.tight_layout()
    callout_out = OUTPUT_DIR / "provider_complexity_callouts.png"
    plt.savefig(callout_out, dpi=300)
    print("Saved callout violin plot:", callout_out)

print("Provider overlap analysis complete. Outputs in:", OUTPUT_DIR)


print("All done. Outputs saved to:", OUTPUT_DIR)
