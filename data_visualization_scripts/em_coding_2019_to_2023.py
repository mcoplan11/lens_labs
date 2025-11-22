#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E/M coding shift analysis, 2019 vs 2023
- Dumbbell chart by specialty
- Ridge plot by state
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
FILE_2023 = "/Users/mitchell_coplan/Downloads/Medicare Physician & Other Practitioners - by Provider and Service/2023/MUP_PHY_R25_P05_V20_D23_Prov_Svc.csv"
FILE_2019 = "/Users/mitchell_coplan/Downloads/Medicare_Physician_Other_Practitioners_by_Provider_and_Service_2019.csv"

# ------------------------
# CONFIG
# ------------------------
files = {
    2019: Path(FILE_2019),
    2023: Path(FILE_2023),
}

em_codes = [str(c) for c in range(99201, 99216)]  # office/outpatient E/M
level4_5 = {"99214", "99215"}  # established, high-level

# ------------------------
# LOAD + PROCESS
# ------------------------
def load_and_aggregate(year, filepath):
    df = pd.read_csv(filepath, dtype=str, low_memory=False)

    # Keep key cols
    df = df[["HCPCS_Cd", "Rndrng_Prvdr_Type",
             "Rndrng_Prvdr_State_Abrvtn", "Tot_Srvcs"]].copy()

    # Clean Tot_Srvcs: remove commas, coerce to numeric
    df["Tot_Srvcs"] = (
        df["Tot_Srvcs"]
        .str.replace(",", "", regex=False)
        .astype(float)  # some files store as "71842.6"
    ).fillna(0).astype(int)

    # Filter E/M
    df = df[df["HCPCS_Cd"].isin(em_codes)]

    # Aggregate by specialty & state
    agg = (
        df.groupby(["Rndrng_Prvdr_Type", "Rndrng_Prvdr_State_Abrvtn", "HCPCS_Cd"], as_index=False)["Tot_Srvcs"]
        .sum()
    )

    # Tag levels
    agg["is_high"] = agg["HCPCS_Cd"].isin(level4_5)
    summary = (
        agg.groupby(["Rndrng_Prvdr_Type", "Rndrng_Prvdr_State_Abrvtn", "is_high"])["Tot_Srvcs"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
        .rename(columns={False: "low", True: "high"})
    )
    summary["total"] = summary["low"] + summary["high"]
    summary["share_high"] = summary["high"] / summary["total"]
    summary["year"] = year
    return summary

df_all = pd.concat([load_and_aggregate(y, f) for y, f in files.items()], ignore_index=True)

# ------------------------
# Dumbbell chart (specialty)
# ------------------------
spec = (
    df_all.groupby(["Rndrng_Prvdr_Type", "year"])[["high", "total"]]   # <-- double brackets!
    .sum()
    .assign(share_high=lambda x: x["high"] / x["total"])
    .reset_index()
    .pivot(index="Rndrng_Prvdr_Type", columns="year", values="share_high")
    .dropna()
    .reset_index()
)


spec["delta"] = spec[2023] - spec[2019]
spec_sorted = spec.sort_values("delta", ascending=False)

plt.figure(figsize=(8, 12))
for i, row in enumerate(spec_sorted.itertuples()):
    plt.plot([row._2, row._3], [i, i], color="gray", lw=1.5)
    plt.scatter(row._2, i, color="blue", s=50, label="2019" if i == 0 else "")
    plt.scatter(row._3, i, color="red", s=50, label="2023" if i == 0 else "")

plt.yticks(range(len(spec_sorted)), spec_sorted["Rndrng_Prvdr_Type"])
plt.xlabel("Share of E/M that are level 4–5")
plt.title("Shift in E/M coding intensity by specialty (2019 vs 2023)")
plt.legend()
plt.tight_layout()
plt.savefig("outputs/em_dumbbell_specialty.png", dpi=300)
plt.close()

# ------------------------
# Ridge plot (states)
# ------------------------
sns.set_theme(style="whitegrid")
plt.figure(figsize=(10, 8))
sns.violinplot(
    data=df_all,
    x="share_high",
    y="Rndrng_Prvdr_State_Abrvtn",
    hue="year",
    split=True,
    inner="quartile",
    scale="width",
    palette={2019: "blue", 2023: "red"},
    order=df_all.groupby("Rndrng_Prvdr_State_Abrvtn")["share_high"].mean().sort_values().index,
)
plt.title("Distribution of high-level E/M coding share by state")
plt.xlabel("Share of visits at level 4–5")
plt.ylabel("State")
plt.tight_layout()
plt.savefig("outputs/em_ridge_states.png", dpi=300)
plt.close()

print("Saved: outputs/em_dumbbell_specialty.png and outputs/em_ridge_states.png")


# ------------------------
# Pick 10 "most interesting" states
# ------------------------
valid_states = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC"
}

state_shift = (
    df_all[df_all["Rndrng_Prvdr_State_Abrvtn"].isin(valid_states)]
    .groupby(["Rndrng_Prvdr_State_Abrvtn", "year"])[["high", "total"]]
    .sum()
    .assign(share_high=lambda x: x["high"] / x["total"])
    .reset_index()
    .pivot(index="Rndrng_Prvdr_State_Abrvtn", columns="year", values="share_high")
    .dropna()
)
state_shift["delta"] = state_shift[2023] - state_shift[2019]
top_states = (
    state_shift["delta"]
    .abs()               # largest absolute changes
    .sort_values(ascending=False)
    .head(10)
    .index.tolist()
)

# ------------------------
# Ridge/violin plot for top states only
# ------------------------
sns.set_theme(style="whitegrid")
plt.figure(figsize=(8, 6))
sns.violinplot(
    data=df_all[df_all["Rndrng_Prvdr_State_Abrvtn"].isin(top_states)],
    x="share_high",
    y="Rndrng_Prvdr_State_Abrvtn",
    hue="year",
    split=True,
    inner="quartile",
    scale="width",
    palette={2019: "blue", 2023: "red"},
    order=state_shift.loc[top_states].sort_values("delta").index,
)
plt.title("E/M coding intensity shifts (top 10 states, 2019–2023)")
plt.xlabel("Share of visits at level 4–5")
plt.ylabel("State")
plt.tight_layout()
plt.savefig("outputs/em_ridge_top10_states.png", dpi=300)
plt.close()