#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analysis of CMS Medicare FFS CERT data:
- Groups claims by HCPCS category (Labs, Imaging, DME, Part B drugs, E/M, Other).
- Calculates disagreement rate = % of claims where Review Decision indicates disagreement.
- Produces a bar chart of disagreement rates by service type.
"""

import pandas as pd
import matplotlib.pyplot as plt

# ----------------------------
# 1. Load CERT dataset
# ----------------------------
# Update this with your actual file path
FILE_CERT = "/Users/mitchell_coplan/Downloads/Medicare_FFS_CERT_2024.csv"
df = pd.read_csv(FILE_CERT)

print("Loaded data shape:", df.shape)
print("Columns:", df.columns.tolist())

# ----------------------------
# 2. Map HCPCS codes to service categories
# ----------------------------
def map_category(hcpcs):
    hcpcs = str(hcpcs)

    if hcpcs.startswith("J") or hcpcs.startswith("Q99"):  
        return "Part B Drugs"
    elif hcpcs.startswith(("E", "K", "L")):  
        return "Durable Medical Equipment"
    elif hcpcs.startswith("7"):  
        return "Imaging"                # 70000-series
    elif hcpcs.startswith("8"):  
        return "Labs"                   # 80000-series
    elif hcpcs.startswith("99"):  
        return "Evaluation & Management"  # 99xxx = E/M
    else:
        return "Other"

df["category"] = df["HCPCS Procedure Code"].astype(str).apply(map_category)

# ----------------------------
# 3. Flag disagreements
# ----------------------------
# Mark claims with disagreement (simple version: any "Disagree" in Review Decision)
df["is_disagree"] = df["Review Decision"].str.contains("Disagree", case=False, na=False)

# ----------------------------
# 4. Aggregate disagreement rates
# ----------------------------
agg = (
    df.groupby("category", as_index=False)
      .agg(
          total_claims=("claim_control_number", "count"),
          disagreed_claims=("is_disagree", "sum")
      )
)
agg["disagreement_rate"] = agg["disagreed_claims"] / agg["total_claims"] * 100

print("\nDisagreement rates by service category:")
print(agg)

# ----------------------------
# 5. Plot results
# ----------------------------
plt.figure(figsize=(8,6))
plt.barh(agg["category"], agg["disagreement_rate"], color="steelblue")
plt.xlabel("Disagreement Rate (%)")
plt.title("Medicare CERT: Claim Disagreement Rate by Service Type")
plt.tight_layout()

# Save + show
plt.savefig("outputs/cert_disagreement_by_service.png", dpi=300)
plt.show()

# ----------------------------
# 6. Export CSV
# ----------------------------
agg.to_csv("outputs/cert_disagreement_by_service.csv", index=False)
