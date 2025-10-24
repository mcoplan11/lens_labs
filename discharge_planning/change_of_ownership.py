"""
Nursing Home Ownership Change Tracker

Dependencies:
    pip install pandas folium geopy selenium reportlab certifi

If you get SSL certificate errors during geocoding, run:
    pip install --upgrade certifi
"""

import pandas as pd
import folium
from geopy.geocoders import Nominatim
from time import sleep
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from pathlib import Path
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import argparse
import ssl
import certifi

# ===================================================================
# CONFIGURATION SECTION - Customize these parameters
# ===================================================================

CONFIG = {
    # Data file paths (update these to your file locations)
    'old_data_path': '/Users/mitchell_coplan/Downloads/nursing_homes_including_rehab_services_06_2025/NH_Ownership_Jun2025.csv',
    'new_data_path': '/Users/mitchell_coplan/Downloads/NH_Ownership_Sep2025.csv',
    'old_month_label': 'June',
    'new_month_label': 'September',

    # Geographic filters (set to None to include all)
    'target_city': 'Chicago',  # e.g., 'HOUSTON' or None for all cities
    'target_state': 'IL',  # e.g., 'TX' or None for all states (Chicago is in IL, not TX!)
    'specific_ccns': None,  # List of CCNs or None, e.g., ['455682', '675791', '676336']

    # Data cleaning thresholds
    'min_ownership_pct_to_report': 1.0,  # Only report owners with >= 1% ownership (lowered from 5%)
    'min_pct_change_threshold': 1.0,  # Only report changes of >= 1 percentage points (lowered from 5%)
    'meaningful_roles': [  # Only report changes for these roles
        '5% or Greater Direct Ownership Interest',
        '5% or Greater Indirect Ownership Interest',
        'Owner',
        'General Partner',
        'Limited Partner',
        'Officer'
    ],
    'exclude_roles': [  # Skip these roles entirely
        'Managing Employee'
    ],

    # Validation settings
    'max_total_ownership_pct': 105.0,  # Flag facilities where total ownership > 105%
    'require_owner_type': True,  # Filter out entries without owner type

    # Output settings
    'output_dir': 'outputs_discharge',
    'output_csv': 'ownership_changes.csv',
    'output_map_html': 'ownership_changes_map.html',
    'output_map_png': 'ownership_changes_map.png',
    'output_pdf': 'ownership_changes_report.pdf',

    # Geocoding settings
    'skip_geocoding': False,  # Set to True to skip map generation entirely
    'use_simple_geocoder': True,  # Use simpler geocoding method if Nominatim fails
}

# ===================================================================
# HELPER FUNCTIONS
# ===================================================================

def clean_pct(x):
    """Clean and normalize ownership percentage values."""
    if pd.isna(x):
        return None
    x = str(x).replace("%", "").strip()
    if x.upper() in ["NOT APPLICABLE", "N/A", ""]:
        return None
    try:
        val = float(x)
        # Validate range
        if val < 0 or val > 100:
            print(f"⚠️  Warning: Invalid ownership percentage: {val}%")
            return None
        return val
    except:
        return None

def parse_location(location_str):
    """Parse location string into city, state, zip."""
    if pd.isna(location_str):
        return None, None, None

    parts = [p.strip() for p in str(location_str).split(",")]

    if len(parts) >= 3:
        # Format: Street, City, State Zip
        city = parts[-3] if len(parts) >= 3 else None
        state_zip = parts[-2] if len(parts) >= 2 else None

        # Extract state (first 2 chars of state_zip)
        state = state_zip.split()[0] if state_zip else None

        return city, state, location_str

    return None, None, location_str

def is_meaningful_change(row, config):
    """Determine if a change is meaningful enough to report."""
    # Check if role is meaningful
    role = row.get('Role played by Owner or Manager in Facility', '')

    # Normalize to uppercase for case-insensitive comparison
    role_upper = role.upper() if role else ''

    # Check exclude list (case-insensitive)
    exclude_roles_upper = [r.upper() for r in config['exclude_roles']]
    if role_upper in exclude_roles_upper:
        return False

    # Check meaningful roles list (case-insensitive)
    if config['meaningful_roles']:
        meaningful_roles_upper = [r.upper() for r in config['meaningful_roles']]
        if role_upper not in meaningful_roles_upper:
            return False

    # Check if ownership percentage meets minimum threshold
    old_pct = row.get(config['old_month_label'], 0) or 0
    new_pct = row.get(config['new_month_label'], 0) or 0

    # For new owners, check if they meet minimum threshold
    if row.get('appeared', False):
        if new_pct < config['min_ownership_pct_to_report']:
            return False

    # For removed owners, check if they met minimum threshold
    if row.get('disappeared', False):
        if old_pct < config['min_ownership_pct_to_report']:
            return False

    # For percentage changes, check if change is significant
    if row.get('pct_changed', False):
        pct_diff = abs(new_pct - old_pct)
        if pct_diff < config['min_pct_change_threshold']:
            return False
        # Also ensure at least one value meets minimum
        if old_pct < config['min_ownership_pct_to_report'] and new_pct < config['min_ownership_pct_to_report']:
            return False

    return True

def validate_facility_ownership(facility_df, config):
    """Check if a facility's total ownership makes sense."""
    # Sum up all direct ownership percentages
    direct_owners = facility_df[
        facility_df['Role played by Owner or Manager in Facility'].str.contains('Direct', na=False)
    ]

    for month in [config['old_month_label'], config['new_month_label']]:
        if month in direct_owners.columns:
            total = direct_owners[month].sum()
            if pd.notna(total) and total > config['max_total_ownership_pct']:
                return False, f"Total ownership in {month} exceeds {config['max_total_ownership_pct']}% ({total:.1f}%)"

    return True, "OK"

def clean_address(addr: str) -> str:
    """Clean address for geocoding."""
    if pd.isna(addr):
        return None
    parts = [p.strip() for p in addr.split(",")]
    return ", ".join(parts)

def simple_geocode(address, city, state):
    """
    Fallback geocoder using approximate city center coordinates.
    Returns (lat, lon) tuple or (None, None) if not found.
    """
    # Common US city centers (add more as needed)
    city_coords = {
        ('CHICAGO', 'IL'): (41.8781, -87.6298),
        ('HOUSTON', 'TX'): (29.7604, -95.3698),
        ('NEW YORK', 'NY'): (40.7128, -74.0060),
        ('LOS ANGELES', 'CA'): (34.0522, -118.2437),
        ('PHOENIX', 'AZ'): (33.4484, -112.0740),
        ('PHILADELPHIA', 'PA'): (39.9526, -75.1652),
        ('SAN ANTONIO', 'TX'): (29.4241, -98.4936),
        ('SAN DIEGO', 'CA'): (32.7157, -117.1611),
        ('DALLAS', 'TX'): (32.7767, -96.7970),
        ('SAN JOSE', 'CA'): (37.3382, -121.8863),
    }

    city_key = (city.upper().strip() if city else '', state.upper().strip() if state else '')

    if city_key in city_coords:
        # Add some random offset so facilities don't stack exactly on top of each other
        import random
        base_lat, base_lon = city_coords[city_key]
        # Small random offset (about 0.01 degrees = ~1km)
        offset_lat = random.uniform(-0.02, 0.02)
        offset_lon = random.uniform(-0.02, 0.02)
        return (base_lat + offset_lat, base_lon + offset_lon)

    return (None, None)

# ===================================================================
# MAIN SCRIPT
# ===================================================================

def main():
    print("="*70)
    print("NURSING HOME OWNERSHIP CHANGE TRACKER")
    print("="*70)

    # Create output directory
    os.makedirs(CONFIG['output_dir'], exist_ok=True)

    # ==== Load data ====
    print(f"\n📂 Loading data...")
    print(f"   Old: {CONFIG['old_data_path']}")
    print(f"   New: {CONFIG['new_data_path']}")

    old_df = pd.read_csv(CONFIG['old_data_path'], dtype=str)
    new_df = pd.read_csv(CONFIG['new_data_path'], dtype=str)

    print(f"\n📊 Data loaded:")
    print(f"   {CONFIG['old_month_label']}: {len(old_df):,} rows, {old_df['CMS Certification Number (CCN)'].nunique():,} unique facilities")
    print(f"   {CONFIG['new_month_label']}: {len(new_df):,} rows, {new_df['CMS Certification Number (CCN)'].nunique():,} unique facilities")

    # ==== Select and clean columns ====
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

    old_df = old_df[cols].copy()
    new_df = new_df[cols].copy()

    # Clean ownership percentages
    for df in [old_df, new_df]:
        df["Ownership Percentage"] = df["Ownership Percentage"].apply(clean_pct)

    # Parse locations
    for df in [old_df, new_df]:
        location_data = df['Location'].apply(parse_location)
        df['City'] = location_data.apply(lambda x: x[0])
        df['State'] = location_data.apply(lambda x: x[1])

    # Tag the months
    old_df["month"] = CONFIG['old_month_label']
    new_df["month"] = CONFIG['new_month_label']

    # ==== Apply geographic filters ====
    print(f"\n🗺️  Applying filters...")

    # Filter old data
    initial_count = len(old_df)
    if CONFIG['target_state']:
        old_df = old_df[old_df['State'].str.strip().str.upper() == CONFIG['target_state'].upper()]
        print(f"   {CONFIG['old_month_label']}: {initial_count:,} → {len(old_df):,} rows (filtered to state: {CONFIG['target_state']})")
        initial_count = len(old_df)

    if CONFIG['target_city']:
        old_df = old_df[old_df['City'].str.strip().str.upper() == CONFIG['target_city'].upper()]
        print(f"   {CONFIG['old_month_label']}: {initial_count:,} → {len(old_df):,} rows (filtered to city: {CONFIG['target_city']})")
        initial_count = len(old_df)

    if CONFIG['specific_ccns']:
        old_df = old_df[old_df['CMS Certification Number (CCN)'].isin(CONFIG['specific_ccns'])]
        print(f"   {CONFIG['old_month_label']}: {initial_count:,} → {len(old_df):,} rows (filtered to specific CCNs)")

    # Filter new data
    initial_count = len(new_df)
    if CONFIG['target_state']:
        new_df = new_df[new_df['State'].str.strip().str.upper() == CONFIG['target_state'].upper()]
        print(f"   {CONFIG['new_month_label']}: {initial_count:,} → {len(new_df):,} rows (filtered to state: {CONFIG['target_state']})")
        initial_count = len(new_df)

    if CONFIG['target_city']:
        new_df = new_df[new_df['City'].str.strip().str.upper() == CONFIG['target_city'].upper()]
        print(f"   {CONFIG['new_month_label']}: {initial_count:,} → {len(new_df):,} rows (filtered to city: {CONFIG['target_city']})")
        initial_count = len(new_df)

    if CONFIG['specific_ccns']:
        new_df = new_df[new_df['CMS Certification Number (CCN)'].isin(CONFIG['specific_ccns'])]
        print(f"   {CONFIG['new_month_label']}: {initial_count:,} → {len(new_df):,} rows (filtered to specific CCNs)")

    # ==== Combine and pivot ====
    combined = pd.concat([old_df, new_df])

    # Create unique key for each owner-role-facility combination
    combined["key"] = (
        combined["CMS Certification Number (CCN)"].astype(str)
        + "|" + combined["Owner Name"].astype(str)
        + "|" + combined["Role played by Owner or Manager in Facility"].astype(str)
    )

    # Pivot to compare across months
    pivot = combined.pivot_table(
        index=[
            "key",
            "CMS Certification Number (CCN)",
            "Provider Name",
            "Owner Name",
            "Role played by Owner or Manager in Facility",
            "Owner Type",
            "Location",
            "City",
            "State"
        ],
        columns="month",
        values="Ownership Percentage",
        aggfunc="first"
    ).reset_index()

    # ==== Detect changes ====
    print(f"\n🔍 Detecting ownership changes...")

    pivot["appeared"] = pivot[CONFIG['old_month_label']].isna() & pivot[CONFIG['new_month_label']].notna()
    pivot["disappeared"] = pivot[CONFIG['new_month_label']].isna() & pivot[CONFIG['old_month_label']].notna()
    pivot["pct_changed"] = (
        pivot[CONFIG['old_month_label']].notna()
        & pivot[CONFIG['new_month_label']].notna()
        & (pivot[CONFIG['old_month_label']] != pivot[CONFIG['new_month_label']])
    )

    # Filter to only changes
    changes = pivot[
        (pivot["appeared"]) | (pivot["disappeared"]) | (pivot["pct_changed"])
    ].copy()

    print(f"   Found {len(changes):,} raw ownership changes")

    # ==== Apply data cleaning filters ====
    print(f"\n🧹 Applying data cleaning filters...")
    print(f"   Minimum ownership to report: {CONFIG['min_ownership_pct_to_report']}%")
    print(f"   Minimum percentage change: {CONFIG['min_pct_change_threshold']} points")
    print(f"   Meaningful roles: {', '.join(CONFIG['meaningful_roles'][:3])}{'...' if len(CONFIG['meaningful_roles']) > 3 else ''}")
    print(f"   Excluded roles: {', '.join(CONFIG['exclude_roles'])}")

    # Show breakdown of raw changes before filtering
    print(f"\n   Raw changes breakdown:")
    print(f"     - Owners appeared: {changes['appeared'].sum()}")
    print(f"     - Owners disappeared: {changes['disappeared'].sum()}")
    print(f"     - Ownership % changed: {changes['pct_changed'].sum()}")

    # Show what roles exist in the data
    print(f"\n   Roles found in changes:")
    role_counts = changes['Role played by Owner or Manager in Facility'].value_counts()
    for role, count in role_counts.head(10).items():
        print(f"     - {role}: {count}")

    # Apply meaningful change filter
    changes['is_meaningful'] = changes.apply(lambda row: is_meaningful_change(row, CONFIG), axis=1)
    meaningful_changes = changes[changes['is_meaningful']].copy()

    print(f"\n   {len(changes):,} → {len(meaningful_changes):,} changes after filtering")

    if len(meaningful_changes) < len(changes):
        filtered_out = len(changes) - len(meaningful_changes)
        print(f"   ({filtered_out} changes filtered out)")

        # Show why they were filtered
        filtered_changes = changes[~changes['is_meaningful']]
        print(f"\n   Top reasons for filtering:")
        # Count by role
        filtered_role_counts = filtered_changes['Role played by Owner or Manager in Facility'].value_counts()
        for role, count in filtered_role_counts.head(5).items():
            print(f"     - Role '{role}': {count} changes")

    # ==== Validate facility ownership ====
    print(f"\n✅ Validating facility ownership totals...")

    facility_validation = {}
    for ccn in meaningful_changes['CMS Certification Number (CCN)'].unique():
        facility_data = pivot[pivot['CMS Certification Number (CCN)'] == ccn]
        is_valid, msg = validate_facility_ownership(facility_data, CONFIG)
        facility_validation[ccn] = {'valid': is_valid, 'message': msg}
        if not is_valid:
            print(f"   ⚠️  CCN {ccn}: {msg}")

    # ==== Generate summary statistics ====
    print(f"\n📈 Summary Statistics:")
    print(f"   Total facilities with changes: {meaningful_changes['CMS Certification Number (CCN)'].nunique()}")
    print(f"   New owners added: {meaningful_changes['appeared'].sum()}")
    print(f"   Owners removed: {meaningful_changes['disappeared'].sum()}")
    print(f"   Ownership % changes: {meaningful_changes['pct_changed'].sum()}")

    if len(meaningful_changes) == 0:
        print("\n✨ No meaningful ownership changes found with current filters.")
        return

    # ==== Save detailed CSV ====
    output_csv_path = os.path.join(CONFIG['output_dir'], CONFIG['output_csv'])
    meaningful_changes.to_csv(output_csv_path, index=False)
    print(f"\n💾 Saved detailed changes to: {output_csv_path}")

    # ==== Print facility summaries ====
    print(f"\n" + "="*70)
    print("FACILITY SUMMARIES")
    print("="*70)

    for (ccn, provider), group in meaningful_changes.groupby(
        ["CMS Certification Number (CCN)", "Provider Name"]
    ):
        city = group['City'].iloc[0] if pd.notna(group['City'].iloc[0]) else 'Unknown'
        state = group['State'].iloc[0] if pd.notna(group['State'].iloc[0]) else 'Unknown'

        print(f"\n🏥 {provider}")
        print(f"   CCN: {ccn} | Location: {city}, {state}")

        # Check validation
        if ccn in facility_validation and not facility_validation[ccn]['valid']:
            print(f"   ⚠️  WARNING: {facility_validation[ccn]['message']}")

        for _, row in group.iterrows():
            if row["appeared"]:
                pct = row[CONFIG['new_month_label']]
                print(f"   ➕ Owner added: {row['Owner Name']}")
                print(f"      Role: {row['Role played by Owner or Manager in Facility']}")
                print(f"      Ownership: {pct:.1f}%" if pd.notna(pct) else "      Ownership: N/A")
            elif row["disappeared"]:
                pct = row[CONFIG['old_month_label']]
                print(f"   ➖ Owner removed: {row['Owner Name']}")
                print(f"      Role: {row['Role played by Owner or Manager in Facility']}")
                print(f"      Ownership: {pct:.1f}%" if pd.notna(pct) else "      Ownership: N/A")
            elif row["pct_changed"]:
                old_pct = row[CONFIG['old_month_label']]
                new_pct = row[CONFIG['new_month_label']]
                diff = new_pct - old_pct if (pd.notna(old_pct) and pd.notna(new_pct)) else None
                print(f"   📊 Ownership changed: {row['Owner Name']}")
                print(f"      Role: {row['Role played by Owner or Manager in Facility']}")
                if diff is not None:
                    print(f"      Change: {old_pct:.1f}% → {new_pct:.1f}% ({diff:+.1f} points)")

    # ==== Geocode and create map ====
    print(f"\n" + "="*70)
    print("GENERATING MAP")
    print("="*70)

    # Get unique facilities (include City and State for fallback geocoding)
    facilities_to_map = meaningful_changes.groupby(
        ['CMS Certification Number (CCN)', 'Provider Name', 'Location', 'City', 'State']
    ).size().reset_index()[['CMS Certification Number (CCN)', 'Provider Name', 'Location', 'City', 'State']]

    if CONFIG['skip_geocoding']:
        print(f"\n⚠️  Geocoding is disabled in CONFIG. Skipping map generation.")
        facilities_to_map['lat'] = [None] * len(facilities_to_map)
        facilities_to_map['lon'] = [None] * len(facilities_to_map)
    else:
        print(f"\n🌍 Geocoding {len(facilities_to_map)} facilities...")

        # Try using Nominatim first
        use_fallback = False
        try:
            ctx = ssl.create_default_context(cafile=certifi.where())
            geolocator = Nominatim(
                user_agent="postacute_watch_v2",
                ssl_context=ctx
            )
        except Exception as e:
            print(f"   ⚠️  Could not initialize Nominatim geocoder: {e}")
            use_fallback = True

        lats, lons = [], []
        geocode_errors = 0
        geocoded_count = 0

        for idx, row in facilities_to_map.iterrows():
            lat, lon = None, None

            # Try Nominatim first if available
            if not use_fallback:
                addr = clean_address(row['Location'])
                try:
                    loc = geolocator.geocode(addr, timeout=10)
                    if loc:
                        lat, lon = loc.latitude, loc.longitude
                        print(f"   ✓ {row['Provider Name']}")
                        geocoded_count += 1
                    else:
                        # Try fallback
                        if CONFIG['use_simple_geocoder']:
                            lat, lon = simple_geocode(
                                row['Location'],
                                row.get('City'),
                                row.get('State')
                            )
                            if lat:
                                print(f"   ✓ {row['Provider Name']} (approximate location)")
                                geocoded_count += 1
                except (ssl.SSLError, Exception) as e:
                    geocode_errors += 1
                    # Use fallback on error
                    if CONFIG['use_simple_geocoder'] and geocode_errors <= 3:
                        if geocode_errors == 3:
                            print(f"   ⚠️  Multiple geocoding errors detected, switching to fallback mode...")
                            use_fallback = True
                        lat, lon = simple_geocode(
                            row['Location'],
                            row.get('City'),
                            row.get('State')
                        )
                        if lat:
                            print(f"   ✓ {row['Provider Name']} (approximate location)")
                            geocoded_count += 1
                    else:
                        print(f"   ⚠️  Error for {row['Provider Name']}")

                if not use_fallback and lat:
                    sleep(1.5)  # Be respectful to Nominatim

            # If using fallback mode
            if use_fallback and not lat:
                lat, lon = simple_geocode(
                    row['Location'],
                    row.get('City'),
                    row.get('State')
                )
                if lat:
                    print(f"   ✓ {row['Provider Name']} (approximate location)")
                    geocoded_count += 1
                else:
                    print(f"   ✗ {row['Provider Name']} (could not geocode)")

            lats.append(lat)
            lons.append(lon)

        print(f"\n   Successfully geocoded {geocoded_count}/{len(facilities_to_map)} facilities")
        if use_fallback:
            print(f"   (Used approximate city-center coordinates)")
        if geocode_errors > 0:
            print(f"   ({geocode_errors} facilities had geocoding errors)")

        facilities_to_map['lat'] = lats
        facilities_to_map['lon'] = lons

    # Merge coordinates back to changes
    meaningful_changes = meaningful_changes.merge(
        facilities_to_map[['CMS Certification Number (CCN)', 'lat', 'lon']],
        on='CMS Certification Number (CCN)',
        how='left'
    )

    # Create map
    facilities_with_coords = meaningful_changes[
        meaningful_changes['lat'].notna() & meaningful_changes['lon'].notna()
    ]

    if len(facilities_with_coords) == 0:
        print("\n⚠️  No facilities could be geocoded. Skipping map and PNG generation.")
        print("     (You can still find the facility details in the CSV output)")
        map_png_path = None
        map_html_path = None
    else:
        print(f"\n🗺️  Creating interactive map with {len(facilities_with_coords)} locations...")

        # Initialize map
        m = folium.Map()
        m.fit_bounds(facilities_with_coords[["lat", "lon"]].values.tolist())

        # Group changes by facility for the popup
        for ccn, facility_group in facilities_with_coords.groupby('CMS Certification Number (CCN)'):
            first_row = facility_group.iloc[0]
            provider_name = first_row['Provider Name']
            lat, lon = first_row['lat'], first_row['lon']

            # Build popup text
            popup_html = f"<b>{provider_name}</b><br>CCN: {ccn}<br><br>"

            for _, row in facility_group.iterrows():
                if row["appeared"]:
                    pct = row[CONFIG['new_month_label']]
                    pct_str = f" ({pct:.1f}%)" if pd.notna(pct) else ""
                    popup_html += f"➕ Added: {row['Owner Name']}{pct_str}<br>"
                elif row["disappeared"]:
                    pct = row[CONFIG['old_month_label']]
                    pct_str = f" ({pct:.1f}%)" if pd.notna(pct) else ""
                    popup_html += f"➖ Removed: {row['Owner Name']}{pct_str}<br>"
                elif row["pct_changed"]:
                    old_pct = row[CONFIG['old_month_label']]
                    new_pct = row[CONFIG['new_month_label']]
                    popup_html += f"📊 {row['Owner Name']}: {old_pct:.1f}% → {new_pct:.1f}%<br>"

            # Add marker
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=provider_name,
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(m)

            # Add label
            folium.Marker(
                [lat, lon],
                icon=folium.DivIcon(html=f"""
                    <div style="font-size: 11px;
                                color: #000;
                                background: rgba(255,255,255,0.9);
                                border: 1px solid #666;
                                border-radius: 3px;
                                padding: 2px 4px;
                                white-space: nowrap;
                                font-weight: 500;">
                        {provider_name}
                    </div>
                """)
            ).add_to(m)

        # Save map
        map_html_path = os.path.join(CONFIG['output_dir'], CONFIG['output_map_html'])
        m.save(map_html_path)
        print(f"   ✓ Map saved to: {map_html_path}")

        # ==== Convert map to PNG ====
        print(f"\n📸 Converting map to PNG...")

        try:
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1600,1000")
            options.add_argument("--force-device-scale-factor=2")

            driver = webdriver.Chrome(options=options)
            map_uri = Path(map_html_path).resolve().as_uri()
            driver.get(map_uri)

            # Wait for map to load
            WebDriverWait(driver, 20).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, ".leaflet-marker-icon")) >= 0
            )
            time.sleep(3)

            # Screenshot
            map_el = driver.find_element(By.CSS_SELECTOR, ".leaflet-container")
            map_png_path = os.path.join(CONFIG['output_dir'], CONFIG['output_map_png'])
            map_el.screenshot(map_png_path)

            driver.quit()
            print(f"   ✓ Screenshot saved to: {map_png_path}")
        except Exception as e:
            print(f"   ⚠️  Could not create PNG screenshot: {e}")
            map_png_path = None

    # ==== Generate PDF Report ====
    print(f"\n📄 Generating PDF report...")

    pdf_path = os.path.join(CONFIG['output_dir'], CONFIG['output_pdf'])
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter

    # Title
    c.setFont("Helvetica-Bold", 18)
    title = f"Nursing Home Ownership Changes"
    c.drawString(72, height - 72, title)

    c.setFont("Helvetica", 11)
    c.drawString(72, height - 95, f"{CONFIG['old_month_label']} to {CONFIG['new_month_label']} Comparison")

    filter_text = ""
    if CONFIG['target_city'] and CONFIG['target_state']:
        filter_text = f"{CONFIG['target_city']}, {CONFIG['target_state']}"
    elif CONFIG['target_state']:
        filter_text = CONFIG['target_state']
    else:
        filter_text = "All Locations"

    c.drawString(72, height - 110, f"Location: {filter_text}")
    c.drawString(72, height - 125, f"Source: CMS Ownership Data")

    # Statistics
    y = height - 155
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "Summary Statistics")
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(72, y, f"Facilities with changes: {meaningful_changes['CMS Certification Number (CCN)'].nunique()}")
    y -= 14
    c.drawString(72, y, f"New owners: {meaningful_changes['appeared'].sum()}")
    y -= 14
    c.drawString(72, y, f"Removed owners: {meaningful_changes['disappeared'].sum()}")
    y -= 14
    c.drawString(72, y, f"Ownership % changes: {meaningful_changes['pct_changed'].sum()}")
    y -= 25

    # Facility summaries
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, "Facility Details")
    y -= 18
    c.setFont("Helvetica", 9)

    for (ccn, provider), group in meaningful_changes.groupby(
        ["CMS Certification Number (CCN)", "Provider Name"]
    ):
        # Check if we need a new page
        if y < 150:
            c.showPage()
            y = height - 72
            c.setFont("Helvetica", 9)

        c.setFont("Helvetica-Bold", 9)
        c.drawString(72, y, f"{provider} (CCN {ccn})")
        y -= 13
        c.setFont("Helvetica", 8)

        for _, row in group.iterrows():
            if y < 80:
                c.showPage()
                y = height - 72
                c.setFont("Helvetica", 8)

            if row["appeared"]:
                pct = row[CONFIG['new_month_label']]
                pct_str = f" ({pct:.1f}%)" if pd.notna(pct) else ""
                line = f"  + Added: {row['Owner Name']}{pct_str}"
            elif row["disappeared"]:
                pct = row[CONFIG['old_month_label']]
                pct_str = f" ({pct:.1f}%)" if pd.notna(pct) else ""
                line = f"  - Removed: {row['Owner Name']}{pct_str}"
            elif row["pct_changed"]:
                old_pct = row[CONFIG['old_month_label']]
                new_pct = row[CONFIG['new_month_label']]
                line = f"  % Changed: {row['Owner Name']} ({old_pct:.1f}% → {new_pct:.1f}%)"
            else:
                line = f"  ? {row['Owner Name']}"

            c.drawString(90, y, line)
            y -= 11
        y -= 8

    # Add map image if available
    if map_png_path and os.path.exists(map_png_path):
        if y < 320:
            c.showPage()
            y = height - 72

        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, y, "Geographic Distribution")
        y -= 10

        try:
            c.drawImage(
                map_png_path,
                72,
                max(72, y - 300),
                width=width - 144,
                height=280,
                preserveAspectRatio=True
            )
        except Exception as e:
            print(f"   ⚠️  Could not add map to PDF: {e}")

    c.save()
    print(f"   ✓ PDF saved to: {pdf_path}")

    print(f"\n" + "="*70)
    print("✅ PROCESSING COMPLETE")
    print("="*70)
    print(f"\nOutput files saved to: {CONFIG['output_dir']}/")
    print(f"  - CSV: {CONFIG['output_csv']}")
    if map_html_path:
        print(f"  - Map: {CONFIG['output_map_html']}")
    if map_png_path and os.path.exists(map_png_path):
        print(f"  - PNG: {CONFIG['output_map_png']}")
    print(f"  - PDF: {CONFIG['output_pdf']}")

    if not map_html_path:
        print(f"\nNote: Map generation was skipped due to geocoding errors.")
        print(f"      To fix SSL errors, try: pip install --upgrade certifi")

if __name__ == "__main__":
    main()
