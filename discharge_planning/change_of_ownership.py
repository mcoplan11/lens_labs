


import pandas as pd

# ==== Load data ====
# Load both months (update filenames as needed)
sept_data = '/Users/mitchell_coplan/Downloads/NH_Ownership_Sep2025.csv'
july_data = '/Users/mitchell_coplan/Downloads/nursing_homes_including_rehab_services_06_2025/NH_Ownership_Jun2025.csv'

july = pd.read_csv(july_data, dtype=str)
sept = pd.read_csv(sept_data, dtype=str)

# print(july)
# print(sept)
print("July rows:", len(july))
print("Sept rows:", len(sept))
print("Unique facilities in July:", july["CMS Certification Number (CCN)"].nunique())
print("Unique facilities in Sept:", sept["CMS Certification Number (CCN)"].nunique())


# Keep consistent columns
cols = [
    "CMS Certification Number (CCN)",
    "Provider Name",
    "Owner Name",
    "Role played by Owner or Manager in Facility",
    "Owner Type",
    "Ownership Percentage",
    "Association Date",
    "Location",
]
july = july[cols].copy()
sept = sept[cols].copy()

# Clean ownership percentage
def clean_pct(x):
    if pd.isna(x):
        return None
    x = str(x).replace("%", "").strip()
    if x.upper() == "NOT APPLICABLE" or x == "":
        return None
    try:
        return float(x)
    except:
        return None

for df in [july, sept]:
    df["Ownership Percentage"] = df["Ownership Percentage"].apply(clean_pct)

# Tag the month
july["month"] = "July"
sept["month"] = "Sept"

# Combine datasets
combined = pd.concat([july, sept])

# Unique key
combined["key"] = (
    combined["CMS Certification Number (CCN)"].astype(str)
    + "|" + combined["Owner Name"].astype(str)
    + "|" + combined["Role played by Owner or Manager in Facility"].astype(str)
)

print(combined.columns)
# Pivot: each owner-role-facility across July & Sept
pivot = combined.pivot_table(
    index=[
        "key",
        "CMS Certification Number (CCN)",
        "Provider Name",
        "Owner Name",
        "Role played by Owner or Manager in Facility",
        "Owner Type",
        "Location"
    ],
    columns="month",
    values="Ownership Percentage",
    aggfunc="first"
).reset_index()

# Detect changes
pivot["appeared"] = pivot["July"].isna() & pivot["Sept"].notna()
pivot["disappeared"] = pivot["Sept"].isna() & pivot["July"].notna()
pivot["pct_changed"] = (
    pivot["July"].notna() & pivot["Sept"].notna() & (pivot["July"] != pivot["Sept"])
)

# Filter
changes = pivot[(pivot["appeared"]) | (pivot["disappeared"]) | (pivot["pct_changed"])].copy()

# === Row-level output ===
print("\n=== Ownership Changes (Row-Level) ===")
# print(changes[[
#     "CMS Certification Number (CCN)",
#     "Location",
#     "Provider Name",
#     "Owner Name",
#     "Role played by Owner or Manager in Facility",
#     "Owner Type",
#     "July",
#     "Sept",
#     "appeared",
#     "disappeared",
#     "pct_changed"
# ]].to_string(index=False))
print(changes)
print(changes['Location'])

changes['City'] = changes['Location'].str.split(',').str[-3]
changes['State'] = changes['Location'].str.split(',').str[-2]

#save to CSV
changes.to_csv("outputs/ownership_changes_july_sept_2025.csv", index=False)

#filter to Houston, TX
changes_houston = changes[changes['City'].str.strip().str.upper() == 'HOUSTON']

# === Facility summary ===
print("\n=== Facility Summaries ===")
for (ccn, provider), group in changes_houston.groupby(["CMS Certification Number (CCN)", "Provider Name"]):
    print(f"\nFacility: {provider} (CCN {ccn})")
    for _, row in group.iterrows():
        if row["appeared"]:
            print(f" - Owner added: {row['Owner Name']} ({row['Sept']}%)")
        elif row["disappeared"]:
            print(f" - Owner removed: {row['Owner Name']} (was {row['July']}%)")
        elif row["pct_changed"]:
            print(f" - Ownership % changed: {row['Owner Name']} ({row['July']}% → {row['Sept']}%)")
