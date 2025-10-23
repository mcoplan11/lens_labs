#!/usr/bin/env python3
"""
Quick test to verify the metadata API works and returns CSV URLs.
"""

import json
import sys

try:
    import requests
except ImportError:
    print("ERROR: requests module not found. Please install: pip install requests")
    sys.exit(1)

DATASET_ID = "4pq5-n9py"
METADATA_URL = f"https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/{DATASET_ID}"

print(f"Fetching metadata from: {METADATA_URL}")
print("-" * 80)

try:
    response = requests.get(METADATA_URL, timeout=30)
    response.raise_for_status()

    metadata = response.json()

    print("✓ Successfully fetched metadata\n")
    print("Dataset Title:", metadata.get("title", "N/A"))
    print("Description:", metadata.get("description", "N/A")[:200] + "...")
    print("\nDistributions found:")
    print("-" * 80)

    distributions = metadata.get("distribution", [])
    for i, dist in enumerate(distributions, 1):
        print(f"\n{i}. Format: {dist.get('format', 'N/A')}")
        print(f"   Media Type: {dist.get('mediaType', 'N/A')}")
        print(f"   Download URL: {dist.get('downloadURL', 'N/A')}")

    # Find CSV URL
    csv_url = None
    for dist in distributions:
        if dist.get("mediaType") == "text/csv":
            csv_url = dist.get("downloadURL")
            break

    if csv_url:
        print("\n" + "=" * 80)
        print("✓ CSV URL FOUND:")
        print("=" * 80)
        print(csv_url)
        print("\nThe script should work correctly with this URL!")
    else:
        print("\n✗ ERROR: No CSV URL found in metadata")
        sys.exit(1)

except requests.RequestException as e:
    print(f"✗ ERROR: Failed to fetch metadata: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ ERROR: {e}")
    sys.exit(1)
