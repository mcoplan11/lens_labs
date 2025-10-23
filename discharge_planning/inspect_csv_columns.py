#!/usr/bin/env python3
"""Quick script to inspect the actual CSV column names from CMS."""

import sys
try:
    import requests
    import pandas as pd
    from io import StringIO
except ImportError as e:
    print(f"ERROR: {e}")
    print("Please install: pip install pandas requests")
    sys.exit(1)

DATASET_ID = "4pq5-n9py"
METADATA_URL = f"https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/{DATASET_ID}"

print("Fetching CSV metadata...")
response = requests.get(METADATA_URL, timeout=30)
metadata = response.json()

csv_url = None
for dist in metadata.get("distribution", []):
    if dist.get("mediaType") == "text/csv":
        csv_url = dist.get("downloadURL")
        break

if not csv_url:
    print("ERROR: No CSV URL found")
    sys.exit(1)

print(f"Downloading CSV from: {csv_url}")
response = requests.get(csv_url, timeout=120)

print(f"Parsing CSV...")
df = pd.read_csv(StringIO(response.text), low_memory=False, nrows=100)

print(f"\n{'='*80}")
print(f"CSV COLUMNS ({len(df.columns)} total)")
print(f"{'='*80}\n")

for i, col in enumerate(df.columns, 1):
    print(f"{i:3d}. {col}")

print(f"\n{'='*80}")
print("SAMPLE DATA (first row)")
print(f"{'='*80}\n")

for col in df.columns:
    value = df[col].iloc[0] if len(df) > 0 else "N/A"
    print(f"{col}: {value}")
