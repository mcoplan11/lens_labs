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

changes['City'] = changes['Location'].str.split(',').str[-3]
changes['State'] = changes['Location'].str.split(',').str[-2]

#save to CSV
changes.to_csv("outputs_discharge/ownership_changes_july_sept_2025.csv", index=False)

#filter to Houston, TX
changes_houston = changes[changes['City'].str.strip().str.upper() == 'HOUSTON']

#only CCN CCN 455682, CCN 675791, CCN 676336
changes_houston = changes_houston[changes_houston['CMS Certification Number (CCN)'].isin(['455682', '675791', '676336'])]
print(changes_houston)

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


# ---------------------
# Geocode addresses (if not already geocoded)
# ---------------------
geolocator = Nominatim(user_agent="postacute_watch")
lats, lons = [], []
def clean_address(addr: str) -> str:
    if pd.isna(addr):
        return None
    # Ensure spaces after commas
    parts = [p.strip() for p in addr.split(",")]
    return ", ".join(parts)

changes_houston["geocode_addr"] = changes_houston["Location"].apply(clean_address)

for addr in changes_houston["geocode_addr"]:
    try:
        loc = geolocator.geocode(addr, timeout=10)
        if loc:
            lats.append(loc.latitude)
            lons.append(loc.longitude)
        else:
            print("⚠️ No match:", addr)
            lats.append(None)
            lons.append(None)
    except Exception as e:
        print("❌ Geocode error:", addr, e)
        lats.append(None)
        lons.append(None)
    sleep(1)  # avoid hammering Nominatim

changes_houston["lat"] = lats
changes_houston["lon"] = lons
print(changes_houston[["geocode_addr", "Location", "lat", "lon"]])
# Hardcode coordinates (fastest for your 3 Houston sites)
coords = {
    "AFTON OAKS NURSING CENTER": (29.6795, -95.3091),  # 7514 Kingsley St
    "BIRCHWOOD OF GOLFCREST": (29.6577, -95.2982),     # 7633 Bellfort
    "CONTINUING CARE AT EAGLES TRACE": (29.7365, -95.6241),  # 14703 Eagle Vista Dr
}

changes_houston["lat"] = changes_houston["Provider Name"].map(lambda x: coords.get(x, (None,None))[0])
changes_houston["lon"] = changes_houston["Provider Name"].map(lambda x: coords.get(x, (None,None))[1])

# ---------------------
# Create interactive Folium map with labels
# ---------------------
import folium

# Initialize map and fit to bounds of all points
m = folium.Map()
m.fit_bounds(changes_houston[["lat", "lon"]].dropna().values.tolist())

for _, row in changes_houston.iterrows():
    if pd.notna(row["lat"]) and pd.notna(row["lon"]):
        # Choose description of the change
        if row["appeared"]:
            change_text = f"Owner added: {row['Owner Name']} ({row['Sept']}%)"
        elif row["disappeared"]:
            change_text = f"Owner removed: {row['Owner Name']} (was {row['July']}%)"
        elif row["pct_changed"]:
            change_text = f"Ownership % changed: {row['Owner Name']} ({row['July']}% → {row['Sept']}%)"
        else:
            change_text = f"Ownership flag: {row['Owner Name']}"

        # Marker with popup
        folium.Marker(
            location=[row["lat"], row["lon"]],
            popup=f"<b>{row['Provider Name']}</b><br>{change_text}",
            tooltip=row["Provider Name"],
            icon=folium.Icon(color="red", icon="plus-sign")
        ).add_to(m)

        # Text label next to pin
        folium.map.Marker(
            [row["lat"], row["lon"]],
            icon=folium.DivIcon(
                html=f"""
                    <div style="font-size: 12px; 
                                color: black; 
                                background:white; 
                                border:1px solid gray; 
                                padding:2px;">
                        {row['Provider Name']}
                    </div>
                """
            )
        ).add_to(m)

# Save map
m.save("outputs_discharge/houston_snf_changes.html")


# ---------------------
# Convert HTML map → PNG (screenshot with Selenium)
# ---------------------
# ----- ensure output dir exists (add this once near the top, before saving files) -----
os.makedirs("outputs_discharge", exist_ok=True)
# ---------------------
# Convert HTML map → PNG (screenshot with Selenium, wait for all pins)
# ---------------------
options = Options()
options.add_argument("--headless=new")
options.add_argument("--window-size=1400,900")
options.add_argument("--force-device-scale-factor=2")  # sharp image

driver = webdriver.Chrome(options=options)

map_html_path = Path("outputs_discharge/houston_snf_changes.html").resolve()
map_uri = map_html_path.as_uri()
driver.get(map_uri)

# How many pins should appear?
expected_markers = len(changes_houston)

# Wait until ALL markers are present
WebDriverWait(driver, 20).until(
    lambda d: len(d.find_elements(By.CSS_SELECTOR, ".leaflet-marker-icon")) >= 0
)

time.sleep(2)  # small buffer for tiles/icons to finish

# Screenshot just the map container (not the full browser window)
map_el = driver.find_element(By.CSS_SELECTOR, ".leaflet-container")
map_el.screenshot("outputs_discharge/houston_snf_changes.png")
print(driver.page_source[:1000])

driver.quit()

# ---------------------
# Build PDF Report
# ---------------------
pdf_path = "outputs_discharge/houston_post_acute_watch.pdf"
c = canvas.Canvas(pdf_path, pagesize=letter)
width, height = letter

# Title
c.setFont("Helvetica-Bold", 20)
c.drawString(72, height - 72, "🏥 Houston Post-Acute Watch – September 2025")

c.setFont("Helvetica", 12)
c.drawString(72, height - 100, "Recent ownership changes for SNFs/LTAC/HHA facilities in the Houston area.")
c.drawString(72, height - 115, "Source: CMS Ownership Data")

# Facility summaries
y = height - 150
c.setFont("Helvetica-Bold", 14)
c.drawString(72, y, "Facility Summaries")
y -= 20
c.setFont("Helvetica", 11)

for (ccn, provider), group in changes_houston.groupby(["CMS Certification Number (CCN)", "Provider Name"]):
    summary_header = f"{provider} (CCN {ccn})"
    c.setFont("Helvetica-Bold", 11)
    c.drawString(72, y, summary_header)
    y -= 15
    c.setFont("Helvetica", 11)
    for _, row in group.iterrows():
        if row["appeared"]:
            line = f"- Owner added: {row['Owner Name']} ({row['Sept']}%)"
        elif row["disappeared"]:
            line = f"- Owner removed: {row['Owner Name']} (was {row['July']}%)"
        elif row["pct_changed"]:
            line = f"- Ownership % changed: {row['Owner Name']} ({row['July']}% → {row['Sept']}%)"
        else:
            line = f"- Ownership flag: {row['Owner Name']}"
        c.drawString(90, y, line)
        y -= 15
    y -= 10

# Insert Map Image (scale to fit)
map_img = "outputs_discharge/houston_snf_changes.png"
c.drawImage(map_img, 72, 72, width=width - 144, height=300, preserveAspectRatio=True)

c.save()

print(f"PDF saved to {pdf_path}")