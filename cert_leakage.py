#!/usr/bin/env python3

"""
Deep-dive on CMS CERT FFS data (your columns):
['claim_control_number','Part','DRG','HCPCS Procedure Code','Provider Type',
 'Type of Bill','Review Decision','Error Code']

Outputs:
- outputs/cert_leakage_matrix.png        (panel: leakage matrix + error mix)
- outputs/cert_error_mix_top5.png        (standalone error mix)
- outputs/cert_leakage_matrix_only.png   (standalone leakage matrix)
- outputs/cert_summary_by_category.csv   (table with metrics)

"""

import os
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from textwrap import wrap

# ----------------------------
# Config
# ----------------------------
INPUT_CSV = "/Users/mitchell_coplan/Downloads/Medicare_FFS_CERT_2024.csv"
OUTDIR = Path("outputs")
OUTDIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Helpers
# ----------------------------
def map_service_category(hcpcs: str) -> str:
    """Map HCPCS/CPT to coarse service buckets for CERT analysis."""
    if pd.isna(hcpcs):
        return "Other"
    s = str(hcpcs).strip().upper()

    # Part B drugs
    if s.startswith("J") or s.startswith("Q99"):
        return "Part B Drugs"

    # DME / supplies
    if s.startswith(("E","K","L")):
        return "Durable Medical Equipment"

    # Imaging (Radiology = 70xxx)
    if s[:1] == "7":   # robust for strings like '71260'
        return "Imaging"

    # Labs (Path/Lab = 80xxx)
    if s[:1] == "8":
        return "Labs"

    # E/M (99xxx)
    if s.startswith("99"):
        return "Evaluation & Management"

    return "Other"


def flag_disagree(text: str) -> bool:
    """Mark any form of disagreement (partial or full)."""
    if pd.isna(text):
        return False
    return "disagree" in str(text).lower()


def flag_partial(text: str) -> bool:
    """Mark partial disagreements specifically."""
    if pd.isna(text):
        return False
    t = str(text).lower()
    return ("partial" in t) and ("disagree" in t)


def map_error_bucket(error_code: str, review_decision: str) -> str:
    """
    Heuristic mapping of CERT error reasons into 4 buckets using both fields.
    Adjust keywords below to fit your file’s vocabulary.
    """
    blob = f"{error_code} {review_decision}".lower()

    # Medical necessity
    if ("medical" in blob and "necess" in blob) or ("not medically necessary" in blob):
        return "Medical Necessity"

    # Documentation-related (insufficient, missing, no documentation)
    if any(k in blob for k in ["insufficient doc", "insufficient documentation",
                               "no documentation", "missing documentation", "record not received"]):
        return "Documentation"

    # Coding / technical (incorrect code, modifier, POS, dx/proc mismatch)
    if any(k in blob for k in ["coding", "code incorrect", "incorrect code", "modifier",
                               "place of service", "pos", "diagnosis", "procedure", "billing error"]):
        return "Coding / Technical"

    # Sometimes the review decision itself carries the signal
    if "necess" in blob:
        return "Medical Necessity"
    if "doc" in blob:
        return "Documentation"
    if "coding" in blob or "modifier" in blob:
        return "Coding / Technical"

    return "Other"

# ----------------------------
# Load data
# ----------------------------
df = pd.read_csv(INPUT_CSV)
needed = ["claim_control_number", "HCPCS Procedure Code", "Review Decision", "Error Code"]
missing = [c for c in needed if c not in df.columns]
if missing:
    raise ValueError(f"Missing required column(s): {missing}. Found: {df.columns.tolist()}")

# ----------------------------
# Derive fields
# ----------------------------
df["category"]       = df["HCPCS Procedure Code"].astype(str).apply(map_service_category)
df["is_disagree"]    = df["Review Decision"].apply(flag_disagree)
df["is_partial_dis"] = df["Review Decision"].apply(flag_partial)

# Only bucket an error reason when there is a disagreement
def safe_error_bucket(row):
    if row["is_disagree"]:
        return map_error_bucket(row["Error Code"], row["Review Decision"])
    else:
        return np.nan

df["error_bucket"] = df.apply(safe_error_bucket, axis=1)


# ----------------------------
# Aggregate by service category
# ----------------------------
total_all_claims = df["claim_control_number"].nunique() if "claim_control_number" in df \
                   else len(df)

grp = (
    df.groupby("category", as_index=False)
      .agg(
          total_claims=("claim_control_number", "count"),
          disagreed_claims=("is_disagree", "sum"),
          partial_disagreed=("is_partial_dis", "sum")
      )
)

grp["disagreement_rate"] = 100 * grp["disagreed_claims"] / grp["total_claims"].clip(lower=1)
grp["partial_share"]     = 100 * grp["partial_disagreed"] / grp["disagreed_claims"].clip(lower=1)
grp["claim_share"]       = 100 * grp["total_claims"] / max(total_all_claims, 1)

# A single scalar to rank “hot spots” = high rate * high volume
grp["leakage_index"]     = grp["disagreement_rate"] * grp["claim_share"] / 100.0

# Sort for tables/labels
grp_sorted = grp.sort_values("leakage_index", ascending=False).reset_index(drop=True)

# ----------------------------
# Error mix within top categories
# ----------------------------
topN = 5
hot_categories = grp_sorted.head(topN)["category"].tolist()
err = (
    df.loc[df["is_disagree"] & df["category"].isin(hot_categories), ["category", "error_bucket"]]
      .assign(error_bucket=lambda x: x["error_bucket"].fillna("Other"))
      .groupby(["category", "error_bucket"], as_index=False)
      .size()
)
# Normalize to shares within category
err["share"] = err.groupby("category")["size"].transform(lambda s: 100 * s / s.sum())

# Keep consistent order
bucket_order = ["Medical Necessity", "Documentation", "Coding / Technical", "Other"]
err["error_bucket"] = pd.Categorical(err["error_bucket"], categories=bucket_order, ordered=True)
err = err.sort_values(["category", "error_bucket"])

# ----------------------------
# Plot 1: Leakage Matrix (rate vs volume share)
# ----------------------------
# Drop "Other" category
plot_data = grp[grp["category"] != "Other"]
plt.figure(figsize=(9,6))
ax = plt.gca()

# Scale bubble sizes down
scale = 2  # tweak until it looks balanced
sizes = plot_data["disagreed_claims"] * scale

# Scatter plot
scatter = ax.scatter(
    plot_data["claim_share"],
    plot_data["disagreement_rate"],
    s=sizes,
    alpha=0.5,
    color="steelblue",
    edgecolor="k",
    linewidth=0.5
)

# Add labels offset from bubbles
for xi, yi, lab in zip(plot_data["claim_share"], plot_data["disagreement_rate"], plot_data["category"]):
    ax.annotate(
        lab, 
        (xi, yi),
        textcoords="offset points",
        xytext=(6,6),
        ha="left",
        fontsize=9,
        weight="bold"
    )

# Labels & formatting
ax.set_xlabel("Share of Unique Claims (%)")
ax.set_ylabel("Disagreement Rate (%)")
ax.set_title("CERT 'Leakage Matrix': Hotspots of Claim Disagreement")
ax.grid(True, linestyle="--", alpha=0.4)

# Ensure bubbles aren’t cut off
ax.set_xlim(0, plot_data["claim_share"].max() * 1.15)
ax.set_ylim(0, plot_data["disagreement_rate"].max() * 1.15)

# Bubble size legend (example values)
for size in [100, 500, 1000]:
    ax.scatter([], [], s=size*scale, c="steelblue", alpha=0.5, edgecolor="k", linewidth=0.5,
               label=f"{size} disagreed claims")
ax.legend(scatterpoints=1, frameon=False, labelspacing=1, title="Bubble Size:")

plt.tight_layout()
plt.savefig(OUTDIR / "cert_leakage_matrix_only.png", dpi=300)


# ----------------------------
# Plot 2: Error mix (stacked bars) for top hot spots
# ----------------------------
fig2, ax2 = plt.subplots(figsize=(9,6))
cats = hot_categories  # preserve leakage ranking
bottom = np.zeros(len(cats))
for b in bucket_order:
    vals = []
    for c in cats:
        v = err.loc[(err["category"] == c) & (err["error_bucket"] == b), "share"]
        vals.append(float(v.iloc[0]) if len(v) else 0.0)
    ax2.barh(cats, vals, left=bottom, label=b)
    bottom += np.array(vals)

ax2.set_xlim(0, 100)
ax2.set_xlabel("Share of Disagreements (%)")
ax2.set_title("Why auditors disagreed (Top 5 hot-spot categories)")
ax2.legend(
    loc="center left",
    bbox_to_anchor=(1.02, 0.5),  # outside right edge
    frameon=False
)
plt.tight_layout()
plt.savefig(OUTDIR / "cert_error_mix_top5.png", dpi=300)

# ----------------------------
# Composite panel (side-by-side)
# ----------------------------
fig = plt.figure(figsize=(15,6))
gs = fig.add_gridspec(1, 2, width_ratios=[1.1, 1])

# Left: Leakage Matrix
axL = fig.add_subplot(gs[0,0])
axL.scatter(x, y, s=sizes, alpha=0.75)
axL.axvline(x_med, ls="--", lw=1, color="gray")
axL.axhline(y_med, ls="--", lw=1, color="gray")
for xi, yi, lab in zip(x, y, labels):
    axL.text(xi+0.5, yi+0.2, lab, fontsize=9)
axL.set_xlabel("Share of All Claims (%)")
axL.set_ylabel("Disagreement Rate (%)")
axL.set_title("A) Leakage Matrix")

# Right: Error Mix stacked bar (Top N)
axR = fig.add_subplot(gs[0,1])
bottom = np.zeros(len(cats))
for b in bucket_order:
    vals = []
    for c in cats:
        v = err.loc[(err["category"] == c) & (err["error_bucket"] == b), "share"]
        vals.append(float(v.iloc[0]) if len(v) else 0.0)
    axR.barh(cats, vals, left=bottom, label=b)
    bottom += np.array(vals)

axR.set_xlim(0, 100)
axR.set_xlabel("Share of Disagreements (%)")
axR.set_title("B) Why Auditors Disagreed (Top 5)")

handles, labels_leg = axR.get_legend_handles_labels()
fig.legend(handles, labels_leg, loc="lower center", ncol=4, frameon=False)
fig.suptitle("\nCERT Hot Spots: Where disagreements concentrate — and why", y=1.02, fontsize=13)

plt.tight_layout()
plt.savefig(OUTDIR / "cert_leakage_matrix.png", dpi=300)

# ----------------------------
# Export table
# ----------------------------
cols = ["category","total_claims","disagreed_claims","disagreement_rate",
        "partial_disagreed","partial_share","claim_share","leakage_index"]
grp_sorted[cols].to_csv(OUTDIR / "cert_summary_by_category.csv", index=False)

print("Saved:")
print(" -", OUTDIR / "cert_leakage_matrix.png")
print(" -", OUTDIR / "cert_leakage_matrix_only.png")
print(" -", OUTDIR / "cert_error_mix_top5.png")
print(" -", OUTDIR / "cert_summary_by_category.csv")
