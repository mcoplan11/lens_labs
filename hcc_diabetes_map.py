#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HCC-proxy choropleth: Diabetes prevalence by US county (CDC PLACES, 2024 release / BRFSS 2022).
- Downloads county-level prevalence for "Diabetes" from CDC PLACES (GIS-friendly dataset, Socrata ID i46a-9kgh)
- Builds an interactive Plotly choropleth (HTML) and a high-res PNG (needs kaleido)
- Prints top/bottom counties + a LinkedIn-ready caption that references HCC v28 Diabetes (HCC 36–38, constrained)

Author: Mitch Coplan
"""

import io
import os
import textwrap
from datetime import datetime

import pandas as pd
import requests
import plotly.express as px

CDC_PLACES_DATASET = "i46a-9kgh"  # County (GIS-friendly) 2024 release
CDC_BASE = f"https://data.cdc.gov/resource/{CDC_PLACES_DATASET}.csv"
COUNTY_GEOJSON_URL = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"

OUT_HTML = "hcc_proxy_diabetes_county_map.html"
OUT_PNG  = "hcc_proxy_diabetes_county_map.png"


def fetch_places_diabetes(year="2024"):
    """Fetch diabetes prevalence by county from CDC PLACES"""
    url = "https://data.cdc.gov/api/views/i46a-9kgh/rows.csv?accessType=DOWNLOAD"
    print("Fetching CDC PLACES diabetes prevalence (county level)...")

    r = requests.get(url, stream=True, timeout=120, verify=False) 
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))

    # Normalize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Detect diabetes prevalence column
    if "diabetes_adjprev" in df.columns:
        df["diabetes_prevalence"] = pd.to_numeric(df["diabetes_adjprev"], errors="coerce")
    elif "diabetes_crudeprev" in df.columns:
        df["diabetes_prevalence"] = pd.to_numeric(df["diabetes_crudeprev"], errors="coerce")
    else:
        raise ValueError("Diabetes prevalence columns not found in CDC PLACES dataset.")

    # Clean FIPS
    df["countyfips"] = df["countyfips"].astype(str).str.zfill(5)
    df = df[df["countyfips"].str.len() == 5]

    # Keep relevant columns
    keep = ["countyfips", "countyname", "stateabbr", "totalpopulation", "diabetes_prevalence"]
    df = df[keep].copy()
    df["year"] = year

    # Drop rows without prevalence
    df = df.dropna(subset=["diabetes_prevalence"])

    return df


def fetch_county_geojson():
    r = requests.get(COUNTY_GEOJSON_URL, timeout=60, verify=False)
    r.raise_for_status()
    return r.json()


def format_caption(df, year=2022):
    pop_thresh = 10000
    df["totalpopulation"] = pd.to_numeric(df["totalpopulation"], errors="coerce")
    stable = df[df["totalpopulation"].fillna(0) > pop_thresh].copy()
    if stable.empty:
        stable = df.copy()

    top = stable.nlargest(10, "diabetes_prevalence")[["countyname","stateabbr","diabetes_prevalence"]]
    bot = stable.nsmallest(10, "diabetes_prevalence")[["countyname","stateabbr","diabetes_prevalence"]]

    top_list = [f"{r.countyname}, {r.stateabbr} ({r.diabetes_prevalence:.1f}%)" for r in top.itertuples(index=False)]
    bot_list = [f"{r.countyname}, {r.stateabbr} ({r.diabetes_prevalence:.1f}%)" for r in bot.itertuples(index=False)]

    hcc_blurb = (
        "In CMS-HCC v28, Diabetes is represented by HCC 36–38; CMS “constrains” these so uncomplicated vs. "
        "complicated diabetes carry the same RAF weight. That makes local diabetes burden especially relevant "
        "when talking population risk."
    )

    caption = f"""
    Diabetes burden varies widely across U.S. counties (CDC PLACES {year}).

    • National median county prevalence: {df['diabetes_prevalence'].median():.1f}%
    • Highest 10 (counties >{pop_thresh:,} pop): {', '.join(top_list)}
    • Lowest 10 (counties >{pop_thresh:,} pop): {', '.join(bot_list)}

    Why this matters for HCCs:
    {hcc_blurb}

    Source: CDC PLACES (county, 2024 release / BRFSS {year}).
    """
    return textwrap.dedent(caption).strip()


def main():
    year = 2024
    df = fetch_places_diabetes(year=year)
    if df.empty:
        raise SystemExit("No data returned from CDC PLACES. Aborting.")

    counties_geo = fetch_county_geojson()

    df["hover"] = df.apply(
        lambda r: f"{r['countyname']}, {r['stateabbr']}<br>Diabetes: {r['diabetes_prevalence']:.1f}%<br>Population: {int(r['totalpopulation']):,}"
        if pd.notnull(r["totalpopulation"]) else
        f"{r['countyname']}, {r['stateabbr']}<br>Diabetes: {r['diabetes_prevalence']:.1f}%",
        axis=1
    )

    fig = px.choropleth(
        df,
        geojson=counties_geo,
        locations="countyfips",
        color="diabetes_prevalence",
        color_continuous_scale="Viridis",
        scope="usa",
        range_color=(df["diabetes_prevalence"].quantile(0.05), df["diabetes_prevalence"].quantile(0.95)),
        hover_name="hover",
        labels={"diabetes_prevalence": "Diabetes (%)"},
        title=f"Diabetes Prevalence by County (CDC PLACES {year}) — HCC-proxy for CMS-HCC v28 Diabetes"
    )
    fig.update_layout(margin=dict(l=0, r=0, t=60, b=0), coloraxis_colorbar=dict(title="Prevalence (%)"))
    fig.add_annotation(text="Hover for details: county, state, prevalence (%), population (if available).",
                       showarrow=False, xref="paper", yref="paper", x=0, y=1.02, xanchor="left", font=dict(size=12))

    print(f"Writing interactive map to ./{OUT_HTML}")
    fig.write_html(OUT_HTML, include_plotlyjs="cdn")

    try:
        print(f"Writing PNG to ./{OUT_PNG}")
        fig.write_image(OUT_PNG, scale=2, width=1400, height=900)
    except Exception as e:
        print("PNG export skipped (install 'kaleido' to enable):", e)

    caption = format_caption(df, year=year)
    print("\n" + "="*80 + "\nLinkedIn caption suggestion\n" + "="*80)
    print(caption)
    print("\nFiles created:", OUT_HTML, "(interactive),", OUT_PNG, "(static PNG if kaleido available)")


if __name__ == "__main__":
    try:
        import plotly  # noqa
    except Exception:
        print("You'll need: pip install pandas requests plotly kaleido")
    main()
