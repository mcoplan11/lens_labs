import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Set global style
plt.style.use("ggplot")
sns.set_context("talk")

# --- Synthetic Example Data (from methodology above) ---

# Example A: COO Shock (velocity and entropy before/after)
weeks = np.arange(6, 22)
claims = np.concatenate([np.random.normal(20, 2, 8),
                         np.random.normal(109, 6, 8)])
entropy = np.concatenate([np.random.normal(2.1, 0.1, 8),
                          np.random.normal(0.77, 0.05, 8)])
coo_week = 14

df_coo = pd.DataFrame({"Week": weeks, "Claims": claims, "Entropy": entropy})

# Example B: IP Synchronization (4 suppliers, same /24, diurnal pattern)
suppliers = ["S-12", "S-17", "S-44", "S-51"]
ip_blocks = ["203.0.113./24"] * 4
diurnal_share = [0.76, 0.78, 0.74, 0.75]
df_ip = pd.DataFrame({
    "Supplier": suppliers,
    "IP Block": ip_blocks,
    "Nocturnal Share": diurnal_share
})

# Example C: Exposed Cohort Exploitation
baseline_rate = 0.05
observed_rate = 0.20
n = 1000
exposed_counts = [np.random.binomial(n, baseline_rate),
                  np.random.binomial(n, observed_rate)]
labels = ["Regional Baseline (5%)", "Cluster Observed (20%)"]

# Example D: Unknown Attack Lens (expected vs observed)
expected = np.random.normal(30, 8, 200)
observed_cluster = [80, 82]
entropy_expected = np.random.normal(1.9, 0.4, 200)
entropy_cluster = [0.2, 0.3]

# --- Plot 1: COO Shock Timeline ---
fig, ax1 = plt.subplots(figsize=(12, 6))
ax1.plot(df_coo["Week"], df_coo["Claims"], marker="o",
         color="steelblue", label="Claims/Week")
ax1.axvline(coo_week, color="red", linestyle="--",
            label="COO Event (Week 14)")
ax1.set_ylabel("Claims per Week", color="steelblue")
ax1.set_xlabel("Week")
ax1.tick_params(axis="y", labelcolor="steelblue")

# Second axis for entropy
ax2 = ax1.twinx()
ax2.plot(df_coo["Week"], df_coo["Entropy"], marker="s",
         color="darkorange", label="SKU Entropy")
ax2.set_ylabel("SKU Entropy", color="darkorange")
ax2.tick_params(axis="y", labelcolor="darkorange")

fig.suptitle("COO Shock: Volume Surge and SKU Narrowing")
fig.legend(loc="upper left", bbox_to_anchor=(0.1, 0.9))
plt.tight_layout()
plt.savefig("fig_coo_shock.png")
plt.close()

# --- Plot 2: IP Synchronization Bar ---
plt.figure(figsize=(8, 6))
sns.barplot(data=df_ip, x="Supplier", y="Nocturnal Share",
            palette="Blues_d")
plt.axhline(0.05, color="red", linestyle="--",
            label="Regional Baseline (5%)")
plt.title("Synchronized Submission: Nocturnal Claim Share (01:00–03:00)")
plt.ylabel("Fraction of Claims in Window")
plt.legend()
plt.tight_layout()
plt.savefig("fig_ip_sync.png")
plt.close()

# --- Plot 3: Exposed Cohort Exploitation ---
plt.figure(figsize=(7, 6))
sns.barplot(x=labels,
            y=[exposed_counts[0]/n, exposed_counts[1]/n],
            palette=["gray", "crimson"])
plt.title("Exposed Cohort Over-indexing")
plt.ylabel("Proportion of Beneficiaries Exposed")
for i, val in enumerate([baseline_rate, observed_rate]):
    plt.text(i, val + 0.01, f"{val:.0%}", ha="center", fontsize=12)
plt.tight_layout()
plt.savefig("fig_exposed.png")
plt.close()

# --- Plot 4 (Updated): Unknown Attack Lens - Novel Submission Pattern ---
# Peers submit claims mostly 8am–6pm, cluster submits mostly 2–4am

# Synthetic data: histogram of submission times
peer_times = np.concatenate([
    np.random.normal(11, 2, 500),  # morning-midday
    np.random.normal(15, 2, 400)   # afternoon
])
peer_times = np.clip(peer_times, 0, 23)  # hours of day

cluster_times = np.random.normal(3, 0.5, 150)  # 3am cluster
cluster_times = np.clip(cluster_times, 0, 23)

plt.figure(figsize=(10, 6))
sns.histplot(peer_times, bins=24, color="steelblue", alpha=0.6, stat="density", label="Peer Cloud")
sns.histplot(cluster_times, bins=24, color="crimson", alpha=0.8, stat="density", label="Cluster (Anomaly)")
plt.xlabel("Hour of Day (Claim Submission Time)")
plt.ylabel("Density")
plt.title("Unknown Attack Lens: Novel Submission Pattern (Cluster at 3am)")
plt.xticks(range(0, 24, 2))
plt.legend()
plt.tight_layout()
plt.savefig("fig_unknown.png")
plt.close()

print("Saved: fig_coo_shock.png, fig_ip_sync.png, fig_exposed.png, fig_unknown.png")
