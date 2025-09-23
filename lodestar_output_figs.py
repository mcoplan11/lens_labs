#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lodestar_mock.py
Creates a synthetic 'Lodestar' investigation card + figures.

Outputs (in ./outputs):
  - lodestar_summary_card.txt           # text summary (copy into a slide/note)
  - lodestar_timeline.png               # claims volume over time + change-point
  - lodestar_feature_contribs.png       # SHAP-style bar of indicator contributions
  - lodestar_entity_heatmap.png         # entity x entity heatmap of shared signals
  - lodestar_sku_concentration.png      # SKU share over time

Customize the "CONFIG" block to change ring size/weights.
"""

import os
import math
import random
from dataclasses import dataclass
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# -------------------------
# CONFIG
# -------------------------
RANDOM_SEED = 7
N_DME = 4
N_PRESCRIBERS = 2
N_BENES = 80
MONTHS = 24
COO_MONTH = 12                 # change-of-ownership event month (0-indexed)
BASELINE_MEAN = 180            # baseline monthly claims
POST_COO_MULT = 1.75           # volume multiplier after COO
SKU_SPACE = ["catheterA", "catheterB", "catheterC", "walker", "brace", "tubing"]
POST_COO_SKU_FOCUS = ["catheterA", "catheterB"]  # SKU narrowing after COO

# Indicator weights (0-1; will be normalized internally)
INDICATOR_WEIGHTS = {
    "post_coo_volume_spike": 1.0,
    "sku_narrowing": 0.9,
    "shared_ip_block": 0.7,
    "shared_mailing_address": 0.6,
    "bene_overlap_cluster": 0.9,
    "velocity_bursts": 0.6,
    "new_provider_identities": 0.5,
}

# Non-nefarious explanation catalog (choose a few based on triggered indicators)
BENIGN_EXPLANATIONS = {
    "post_coo_volume_spike": "Legit new ownership ramp (marketing push, new referral partners).",
    "sku_narrowing": "Clinical mix shift (e.g., new post-acute contracts) or formulary changes.",
    "shared_ip_block": "Shared billing vendor or managed service using NAT.",
    "shared_mailing_address": "Consolidated mailroom or P.O. box for a management company.",
    "bene_overlap_cluster": "Regional disease outbreak or localized outreach program.",
    "velocity_bursts": "Seasonality, supplier backlog clearing, or EMR batch submission.",
    "new_provider_identities": "Acquisitions, locums placements, or credentialing transitions.",
}

# -------------------------
# UTILITIES
# -------------------------
np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def softmax(x: np.ndarray) -> np.ndarray:
    ex = np.exp(x - np.max(x))
    return ex / ex.sum()

def normalize_0_1(x: np.ndarray) -> np.ndarray:
    mn, mx = np.min(x), np.max(x)
    if mx == mn:
        return np.zeros_like(x)
    return (x - mn) / (mx - mn)

# -------------------------
# SYNTHETIC DATA GENERATION
# -------------------------
@dataclass
class Entity:
    id: str
    type: str  # "DME" or "Prescriber"

def synth_ring(n_dme: int, n_prescribers: int) -> Tuple[List[Entity], List[Entity]]:
    dmes = [Entity(id=f"DME_{i+1}", type="DME") for i in range(n_dme)]
    pres = [Entity(id=f"PRV_{i+1}", type="Prescriber") for i in range(n_prescribers)]
    return dmes, pres

def synth_monthly_claims(months: int, baseline: int, post_mult: float, coo_m: int) -> np.ndarray:
    base = np.random.poisson(lam=baseline, size=months).astype(float)
    # Add mild trend + noise
    drift = np.linspace(-10, 15, months)
    noise = np.random.normal(0, 8, months)
    base = np.clip(base + drift + noise, 20, None)
    # Apply change-of-ownership jump
    base[coo_m:] *= post_mult
    return base

def synth_sku_mix(months: int, skus: List[str], focus: List[str], coo_m: int) -> pd.DataFrame:
    """
    Returns DataFrame with columns: month, sku, share (sums to 1 by month).
    Pre-COO: diverse mix. Post-COO: concentrates into 'focus' SKUs.
    """
    rows = []
    for m in range(months):
        if m < coo_m:
            logits = np.random.normal(0, 0.6, len(skus))
        else:
            logits = np.array([1.5 if s in focus else -0.6 for s in skus]) + np.random.normal(0, 0.3, len(skus))
        share = softmax(logits)
        for s, p in zip(skus, share):
            rows.append({"month": m, "sku": s, "share": p})
    return pd.DataFrame(rows)

def synth_shared_signals(dmes: List[Entity], pres: List[Entity]) -> Dict[str, Dict[str, int]]:
    """
    Fake 'shared' features counts between entities: shared IPs, addresses, bene overlap.
    Returns a dict keyed by indicator to a square matrix (pandas DataFrame) of intensity.
    """
    entities = dmes + pres
    n = len(entities)
    base = np.random.randint(0, 2, size=(n, n))
    base = np.maximum(base, base.T)  # symmetric

    # Intensify inside the DME cluster to suggest a ring
    for i, e_i in enumerate(entities):
        for j, e_j in enumerate(entities):
            if i >= j: 
                continue
            if e_i.type == "DME" and e_j.type == "DME":
                if np.random.rand() < 0.7:
                    base[i, j] = base[j, i] = 1

    # Layer individual signal matrices
    def jitter(mat, p):
        out = mat.copy().astype(float)
        noise = np.random.binomial(1, p, size=out.shape)
        out = np.clip(out + noise, 0, 2)
        return out

    mats = {
        "shared_ip_block": jitter(base, 0.15),
        "shared_mailing_address": jitter(base, 0.10),
        "bene_overlap_cluster": jitter(base, 0.20),
    }
    # to DataFrames with labels
    labels = [e.id for e in entities]
    return {k: pd.DataFrame(v, index=labels, columns=labels) for k, v in mats.items()}

def synth_velocity(months: int, series: np.ndarray) -> float:
    """
    Simple velocity burst score: fraction of months where month over month jump > threshold.
    """
    diffs = np.diff(series)
    thresh = np.percentile(np.abs(diffs), 75)  # top quartile changes
    bursts = (diffs > thresh).mean()
    return float(bursts)

def sku_narrowing_score(sku_df: pd.DataFrame, coo_m: int) -> float:
    """
    1 - (post-COO entropy / pre-COO entropy) -> higher = narrower post COO.
    """
    def entropy(shares):
        s = np.clip(shares, 1e-9, 1.0)
        return -np.sum(s * np.log(s))
    pre = sku_df[sku_df["month"] < coo_m].groupby("sku")["share"].mean().values
    post = sku_df[sku_df["month"] >= coo_m].groupby("sku")["share"].mean().values
    return float(1.0 - (entropy(post) / max(entropy(pre), 1e-6)))

def coo_spike_score(series: np.ndarray, coo_m: int) -> float:
    pre = series[:coo_m].mean()
    post = series[coo_m:].mean()
    if pre <= 0:
        return 0.0
    return float((post - pre) / pre)

def shared_signal_strength(mats: Dict[str, pd.DataFrame]) -> Dict[str, float]:
    return {k: float((v.values[np.triu_indices_from(v.values, 1)] > 0).mean()) for k, v in mats.items()}

# -------------------------
# RISK SCORING
# -------------------------
def weighted_risk(indicators: Dict[str, float], weights: Dict[str, float]) -> Tuple[float, Dict[str, float]]:
    # normalize indicators to 0-1 per indicator via clipping
    norm_ind = {k: float(np.clip(v, 0, 1)) for k, v in indicators.items()}
    w = np.array([weights[k] for k in norm_ind.keys()], dtype=float)
    w = w / (w.sum() + 1e-9)
    x = np.array([norm_ind[k] for k in norm_ind.keys()], dtype=float)
    contrib = w * x
    score = float(contrib.sum())
    # map back contributions
    return score, {k: float(c) for k, c in zip(norm_ind.keys(), contrib)}

def pick_benign_explanations(indicators: Dict[str, float], k=3) -> List[str]:
    # choose explanations for highest indicators
    top = sorted(indicators.items(), key=lambda kv: kv[1], reverse=True)
    picks = []
    for name, _ in top:
        if name in BENIGN_EXPLANATIONS and BENIGN_EXPLANATIONS[name] not in picks:
            picks.append(BENIGN_EXPLANATIONS[name])
        if len(picks) >= k:
            break
    return picks

# -------------------------
# PLOTTING
# -------------------------
def plot_timeline(series: np.ndarray, coo_m: int, outpath: str):
    plt.figure(figsize=(10, 4))
    plt.plot(np.arange(len(series)), series, linewidth=2)
    plt.axvline(coo_m, linestyle="--")
    plt.title("Claims volume over time (COO flagged)")
    plt.xlabel("Month")
    plt.ylabel("Claims")
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()

def plot_feature_contribs(contribs: Dict[str, float], outpath: str):
    names = list(contribs.keys())
    vals = np.array(list(contribs.values()))
    order = np.argsort(vals)
    plt.figure(figsize=(7, 4.5))
    plt.barh(np.array(names)[order], vals[order])
    plt.xlabel("Contribution to risk")
    plt.title("Indicator contributions")
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()

def plot_entity_heatmap(mats: Dict[str, pd.DataFrame], outpath: str):
    # Combine signals into a single intensity matrix for display
    keys = list(mats.keys())
    combo = sum(mats[k].values for k in keys) / max(len(keys), 1)
    labels = list(mats[keys[0]].index)
    plt.figure(figsize=(6.5, 5.5))
    plt.imshow(combo, aspect='auto')
    plt.xticks(ticks=np.arange(len(labels)), labels=labels, rotation=45, ha='right')
    plt.yticks(ticks=np.arange(len(labels)), labels=labels)
    plt.colorbar(label="Shared-signal intensity")
    plt.title("Entity connectivity (IP / address / bene overlap)")
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()

def plot_sku_concentration(sku_df: pd.DataFrame, outpath: str):
    # show share of focal SKUs over time
    focus = (sku_df[sku_df["sku"].isin(POST_COO_SKU_FOCUS)]
             .groupby("month")["share"].sum().reset_index())
    plt.figure(figsize=(8, 3.5))
    plt.plot(focus["month"], focus["share"], linewidth=2)
    plt.ylim(0, 1)
    plt.title("Focus SKU share over time")
    plt.xlabel("Month")
    plt.ylabel("Share")
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()

# -------------------------
# MAIN
# -------------------------
def main():
    ensure_dir("outputs")

    # 1) Entities
    dmes, pres = synth_ring(N_DME, N_PRESCRIBERS)
    entities = dmes + pres

    # 2) Time series + SKU mix
    series = synth_monthly_claims(MONTHS, BASELINE_MEAN, POST_COO_MULT, COO_MONTH)
    sku_df = synth_sku_mix(MONTHS, SKU_SPACE, POST_COO_SKU_FOCUS, COO_MONTH)

    # 3) Shared signals
    mats = synth_shared_signals(dmes, pres)

    # 4) Indicators
    indicators = {}
    indicators["post_coo_volume_spike"] = coo_spike_score(series, COO_MONTH)             # ~0..1+
    indicators["sku_narrowing"] = np.clip(sku_narrowing_score(sku_df, COO_MONTH), 0, 1)  # 0..1
    ss = shared_signal_strength(mats)
    indicators.update(ss)                                                                 # 0..1-ish
    indicators["velocity_bursts"] = synth_velocity(MONTHS, series)                        # 0..1
    indicators["new_provider_identities"] = float(np.random.beta(2, 5))                   # proxy

    # 5) Score + contributions
    risk_score_0_1, contribs = weighted_risk(indicators, INDICATOR_WEIGHTS)
    overall_risk_percent = int(round(100 * np.clip(risk_score_0_1, 0, 1)))

    # 6) Build “why surfaced” (top contributing reasons)
    why = sorted(contribs.items(), key=lambda kv: kv[1], reverse=True)
    top_why = [f"{k.replace('_',' ')}" for k, _ in why[:4]]

    # 7) Benign explanations
    benign = pick_benign_explanations(indicators, k=3)

    # 8) Save figures
    plot_timeline(series, COO_MONTH, "outputs/lodestar_timeline.png")
    plot_feature_contribs(contribs, "outputs/lodestar_feature_contribs.png")
    plot_entity_heatmap(mats, "outputs/lodestar_entity_heatmap.png")
    plot_sku_concentration(sku_df, "outputs/lodestar_sku_concentration.png")

    # 9) Assemble ring roster + joined signals per entity
    #    Show, for each DME, what it shares with others (IP/address/bene overlap)
    def summarize_entity(eid: str) -> Dict[str, str]:
        row = {}
        for sig, df in mats.items():
            # sum of connections from eid to others
            s = df.loc[eid].copy()
            s = s.drop(eid, errors="ignore")
            row[sig] = f"{int((s>0).sum())} links"
        return row

    roster_rows = []
    for e in entities:
        row = {"entity": e.id, "type": e.type}
        row.update(summarize_entity(e.id))
        roster_rows.append(row)
    roster = pd.DataFrame(roster_rows)

    # 10) Text summary card
    summary_lines = []
    summary_lines.append("=== Lodestar – Mock Investigation Card ===")
    summary_lines.append(f"Overall Risk: {overall_risk_percent}%")
    summary_lines.append("")
    summary_lines.append("Ring roster (entities & shared-signal links):")
    summary_lines.append(roster.to_string(index=False))
    summary_lines.append("")
    summary_lines.append("Why we surfaced this:")
    for s in top_why:
        summary_lines.append(f"  • {s}")
    summary_lines.append("")
    summary_lines.append("Possible non-nefarious explanations:")
    for b in benign:
        summary_lines.append(f"  • {b}")
    summary_lines.append("")
    summary_lines.append("Figures saved:")
    summary_lines.append("  • outputs/lodestar_timeline.png")
    summary_lines.append("  • outputs/lodestar_feature_contribs.png")
    summary_lines.append("  • outputs/lodestar_entity_heatmap.png")
    summary_lines.append("  • outputs/lodestar_sku_concentration.png")

    with open("outputs/lodestar_summary_card.txt", "w") as f:
        f.write("\n".join(summary_lines))

    # Also print to console for quick copy/paste
    print("\n".join(summary_lines))

if __name__ == "__main__":
    main()
