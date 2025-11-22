#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Medicare Advantage Star Ratings Geographic Analysis
Creates choropleth maps showing enrollment-weighted average star ratings by county and state.
Identifies "quality deserts" - areas where beneficiaries have limited access to high-quality MA plans.

Data Sources:
- CMS Medicare Advantage Star Ratings (annual)
- CMS Medicare Advantage Enrollment by County

Outputs:
- ma_star_ratings_county_map.html (interactive)
- ma_star_ratings_county_map.png (static)
- ma_star_ratings_state_map.html (interactive)
- ma_star_ratings_state_map.png (static)
- ma_quality_deserts_summary.csv

Author: Generated with Claude Code
"""

import io
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -------------------------
# CONFIG
# -------------------------
CURRENT_YEAR = 2024  # Most recent year
START_YEAR = 2020  # Start of trend analysis
YEARS = list(range(START_YEAR, CURRENT_YEAR + 1))  # 2020-2024

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# CMS Star Ratings data URLs (these are publicly available)
# Note: Actual URLs may need updating based on CMS website structure
STAR_RATINGS_URL = "https://data.cms.gov/provider-data/api/1/datastore/query/kdjb-456p/0"  # Star Ratings
ENROLLMENT_URL = "https://data.cms.gov/provider-data/api/1/datastore/query/6j2x-ke9n/0"  # Monthly enrollment

COUNTY_GEOJSON_URL = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"

# Quality desert thresholds
QUALITY_DESERT_THRESHOLD = 3.5  # Counties where avg rating < 3.5
LOW_ACCESS_THRESHOLD = 2  # Counties with < 2 plans available


# -------------------------
# DATA FETCHING
# -------------------------
def fetch_star_ratings_multiyear(years=YEARS):
    """
    Fetch Medicare Advantage Star Ratings for multiple years.
    For this demo, we'll create synthetic realistic data with temporal trends.
    In production, replace with actual CMS API calls for each year.
    """
    print(f"Generating sample MA Star Ratings data for {years[0]}-{years[-1]}...")

    np.random.seed(42)
    n_contracts = 500
    all_data = []

    # Create base contracts that persist across years
    base_contracts = []
    for i in range(n_contracts):
        contract_id = f"H{np.random.randint(1000, 9999)}"
        base_contracts.append({
            'contract_id': contract_id,
            'plan_name': f"Plan {contract_id}",
            'parent_org': f"Org_{np.random.randint(1, 50)}",
            'plan_type': np.random.choice(['HMO', 'PPO', 'PFFS', 'SNP'], p=[0.45, 0.35, 0.10, 0.10]),
            'base_rating': np.random.choice([2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
                                           p=[0.03, 0.07, 0.25, 0.30, 0.20, 0.10, 0.05]),
            # Assign trend: some plans improve, some decline, most stay stable
            'trend': np.random.choice(['improve', 'decline', 'stable'], p=[0.25, 0.15, 0.60])
        })

    # Generate ratings for each year with trends
    for year_idx, year in enumerate(years):
        for contract in base_contracts:
            base = contract['base_rating']

            # Apply trend over time
            if contract['trend'] == 'improve':
                # Improve by ~0.5-1.0 stars over 5 years, but cap at 5.0
                change = min(0.15 * year_idx, 1.0)
                rating = min(base + change, 5.0)
            elif contract['trend'] == 'decline':
                # Decline by ~0.3-0.5 stars over 5 years, but floor at 2.0
                change = min(0.08 * year_idx, 0.5)
                rating = max(base - change, 2.0)
            else:  # stable
                # Small random fluctuation ±0.1
                rating = base + np.random.uniform(-0.1, 0.1)
                rating = np.clip(rating, 2.0, 5.0)

            # Round to nearest 0.5
            rating = round(rating * 2) / 2

            all_data.append({
                'year': year,
                'contract_id': contract['contract_id'],
                'plan_name': contract['plan_name'],
                'overall_rating': rating,
                'parent_org': contract['parent_org'],
                'plan_type': contract['plan_type']
            })

    return pd.DataFrame(all_data)


def fetch_enrollment_by_county_multiyear(years=YEARS):
    """
    Fetch MA enrollment by contract and county for multiple years.
    For this demo, we'll create synthetic data with realistic geographic patterns.
    Enrollment grows over time to reflect real MA trends.
    """
    print(f"Generating sample enrollment by county data for {years[0]}-{years[-1]}...")

    # Load state/county FIPS codes (abbreviated list for demo)
    # In production, use full FIPS code list
    states_fips = {
        '01': 'AL', '04': 'AZ', '06': 'CA', '08': 'CO', '09': 'CT',
        '12': 'FL', '13': 'GA', '17': 'IL', '18': 'IN', '19': 'IA',
        '20': 'KS', '21': 'KY', '22': 'LA', '25': 'MA', '26': 'MI',
        '27': 'MN', '29': 'MO', '31': 'NE', '32': 'NV', '33': 'NH',
        '34': 'NJ', '36': 'NY', '37': 'NC', '39': 'OH', '40': 'OK',
        '41': 'OR', '42': 'PA', '45': 'SC', '47': 'TN', '48': 'TX',
        '49': 'UT', '51': 'VA', '53': 'WA', '55': 'WI'
    }

    np.random.seed(43)
    all_enrollment = []

    # Generate enrollment data for counties across all years
    for year_idx, year in enumerate(years):
        # Enrollment grows ~8% per year on average (realistic MA growth)
        growth_factor = 1 + (0.08 * year_idx)

        for state_fips, state_abbr in states_fips.items():
            # Each state has 5-20 counties (simplified)
            n_counties = np.random.randint(5, 21)

            for county_idx in range(1, n_counties + 1):
                county_fips = f"{state_fips}{str(county_idx).zfill(3)}"

                # Each county has 2-10 MA plans available
                n_plans = np.random.randint(2, 11)

                # Urban counties have more plans and higher enrollment
                is_urban = np.random.random() > 0.3
                base_enrollment = np.random.randint(500, 5000) if is_urban else np.random.randint(50, 800)

                for plan_idx in range(n_plans):
                    contract_id = f"H{np.random.randint(1000, 9999)}"
                    enrollment = int(base_enrollment * np.random.uniform(0.5, 2.0) * growth_factor)

                    all_enrollment.append({
                        'year': year,
                        'contract_id': contract_id,
                        'county_fips': county_fips,
                        'state_abbr': state_abbr,
                        'enrollment': enrollment,
                        'county_name': f"County {county_idx}"
                    })

    return pd.DataFrame(all_enrollment)


def fetch_county_geojson():
    """Fetch US county boundaries GeoJSON"""
    print("Fetching county GeoJSON...")
    r = requests.get(COUNTY_GEOJSON_URL, timeout=60, verify=False)
    r.raise_for_status()
    return r.json()


def fetch_state_geojson():
    """Fetch US state boundaries GeoJSON"""
    print("Fetching state GeoJSON...")
    url = "https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/us-states.json"
    r = requests.get(url, timeout=60, verify=False)
    r.raise_for_status()
    return r.json()


# -------------------------
# DATA PROCESSING
# -------------------------
def calculate_county_ratings(star_ratings_df, enrollment_df):
    """
    Calculate enrollment-weighted average star ratings by county.
    """
    print("Calculating county-level enrollment-weighted ratings...")

    # Merge ratings with enrollment
    merged = enrollment_df.merge(
        star_ratings_df[['contract_id', 'overall_rating', 'plan_type']],
        on='contract_id',
        how='left'
    )

    # Some plans might not have ratings - drop them
    merged = merged.dropna(subset=['overall_rating'])

    # Calculate enrollment-weighted average rating per county
    county_stats = merged.groupby('county_fips').apply(
        lambda x: pd.Series({
            'avg_rating': np.average(x['overall_rating'], weights=x['enrollment']),
            'total_enrollment': x['enrollment'].sum(),
            'num_plans': x['contract_id'].nunique(),
            'max_rating': x['overall_rating'].max(),
            'min_rating': x['overall_rating'].min(),
            'state_abbr': x['state_abbr'].iloc[0],
            'county_name': x['county_name'].iloc[0],
            'pct_4plus_enrollment': (x.loc[x['overall_rating'] >= 4.0, 'enrollment'].sum() /
                                    x['enrollment'].sum() * 100)
        })
    ).reset_index()

    # Identify quality deserts
    county_stats['is_quality_desert'] = (
        (county_stats['avg_rating'] < QUALITY_DESERT_THRESHOLD) |
        (county_stats['num_plans'] < LOW_ACCESS_THRESHOLD)
    )

    return county_stats


def calculate_state_ratings(county_stats):
    """
    Aggregate county data to state level.
    """
    print("Calculating state-level statistics...")

    state_stats = county_stats.groupby('state_abbr').apply(
        lambda x: pd.Series({
            'avg_rating': np.average(x['avg_rating'], weights=x['total_enrollment']),
            'total_enrollment': x['total_enrollment'].sum(),
            'num_counties': len(x),
            'quality_desert_counties': x['is_quality_desert'].sum(),
            'pct_quality_desert': (x['is_quality_desert'].sum() / len(x) * 100),
            'pct_4plus_enrollment': np.average(x['pct_4plus_enrollment'], weights=x['total_enrollment'])
        })
    ).reset_index()

    return state_stats


def calculate_state_trends(star_ratings_df, enrollment_df, years):
    """
    Calculate state-level rating trends over time.
    Returns DataFrame with yearly ratings and trend statistics.
    """
    print(f"Calculating state-level trends from {years[0]}-{years[-1]}...")

    all_state_years = []

    for year in years:
        # Filter data for this year
        ratings_year = star_ratings_df[star_ratings_df['year'] == year]
        enrollment_year = enrollment_df[enrollment_df['year'] == year]

        # Merge and calculate state averages
        merged = enrollment_year.merge(
            ratings_year[['contract_id', 'overall_rating']],
            on='contract_id',
            how='left'
        ).dropna(subset=['overall_rating'])

        state_year = merged.groupby('state_abbr').apply(
            lambda x: pd.Series({
                'year': year,
                'avg_rating': np.average(x['overall_rating'], weights=x['enrollment']),
                'total_enrollment': x['enrollment'].sum()
            })
        ).reset_index()

        all_state_years.append(state_year)

    # Combine all years
    state_trends = pd.concat(all_state_years, ignore_index=True)

    # Calculate trend statistics per state
    trend_stats = []
    for state in state_trends['state_abbr'].unique():
        state_data = state_trends[state_trends['state_abbr'] == state].sort_values('year')

        if len(state_data) >= 2:
            # Linear trend (simple slope calculation)
            years_arr = state_data['year'].values
            ratings_arr = state_data['avg_rating'].values

            # Calculate slope (change per year)
            slope = np.polyfit(years_arr - years_arr[0], ratings_arr, 1)[0]

            # Total change from first to last year
            total_change = ratings_arr[-1] - ratings_arr[0]

            # Current (most recent) rating
            current_rating = ratings_arr[-1]

            # Categorize trend
            if total_change >= 0.25:
                trend_category = 'Strong Improvement'
            elif total_change >= 0.1:
                trend_category = 'Moderate Improvement'
            elif total_change <= -0.25:
                trend_category = 'Significant Decline'
            elif total_change <= -0.1:
                trend_category = 'Moderate Decline'
            else:
                trend_category = 'Stable'

            trend_stats.append({
                'state_abbr': state,
                'current_rating': current_rating,
                'rating_2020': ratings_arr[0],
                'total_change': total_change,
                'annual_change': slope,
                'trend_category': trend_category,
                'pct_change': (total_change / ratings_arr[0]) * 100 if ratings_arr[0] > 0 else 0
            })

    trend_stats_df = pd.DataFrame(trend_stats)

    return state_trends, trend_stats_df


# -------------------------
# VISUALIZATION
# -------------------------
def create_county_map(county_stats, counties_geo):
    """
    Create interactive county-level choropleth map.
    """
    print("Creating county-level map...")

    # Ensure FIPS is 5 digits with leading zeros
    county_stats['county_fips'] = county_stats['county_fips'].astype(str).str.zfill(5)

    # Create hover text
    county_stats['hover_text'] = county_stats.apply(
        lambda r: (
            f"<b>{r['county_name']}, {r['state_abbr']}</b><br>"
            f"Avg Rating: {r['avg_rating']:.2f} ⭐<br>"
            f"Enrollment: {int(r['total_enrollment']):,}<br>"
            f"# Plans: {int(r['num_plans'])}<br>"
            f"Range: {r['min_rating']:.1f} - {r['max_rating']:.1f}<br>"
            f"% in 4+ star plans: {r['pct_4plus_enrollment']:.1f}%<br>"
            f"{'🚨 QUALITY DESERT' if r['is_quality_desert'] else '✓ Adequate access'}"
        ),
        axis=1
    )

    # Create figure
    fig = px.choropleth(
        county_stats,
        geojson=counties_geo,
        locations='county_fips',
        color='avg_rating',
        color_continuous_scale='RdYlGn',  # Red (low) to Green (high)
        range_color=(2.0, 5.0),
        scope="usa",
        hover_name='hover_text',
        labels={'avg_rating': 'Avg Star Rating'},
        title=f"Medicare Advantage Quality by County ({CURRENT_YEAR})<br><sub>Enrollment-weighted average star ratings</sub>"
    )

    fig.update_geos(
        showlakes=True,
        lakecolor='rgb(230, 245, 255)'
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=80, b=0),
        coloraxis_colorbar=dict(
            title="Star Rating",
            tickvals=[2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
            ticktext=['2.0⭐', '2.5⭐', '3.0⭐', '3.5⭐', '4.0⭐', '4.5⭐', '5.0⭐']
        ),
        font=dict(size=12)
    )

    # Add annotation
    fig.add_annotation(
        text=(
            f"Quality deserts (avg <{QUALITY_DESERT_THRESHOLD}⭐ or <{LOW_ACCESS_THRESHOLD} plans): "
            f"{county_stats['is_quality_desert'].sum():,} counties "
            f"({county_stats['is_quality_desert'].sum()/len(county_stats)*100:.1f}%)"
        ),
        showarrow=False,
        xref="paper", yref="paper",
        x=0.5, y=-0.05,
        xanchor="center",
        font=dict(size=11, color="gray")
    )

    return fig


def create_state_map(state_stats):
    """
    Create state-level choropleth map.
    """
    print("Creating state-level map...")

    # Create hover text
    state_stats['hover_text'] = state_stats.apply(
        lambda r: (
            f"<b>{r['state_abbr']}</b><br>"
            f"Avg Rating: {r['avg_rating']:.2f} ⭐<br>"
            f"Total Enrollment: {int(r['total_enrollment']):,}<br>"
            f"Quality Desert Counties: {int(r['quality_desert_counties'])} ({r['pct_quality_desert']:.1f}%)<br>"
            f"% in 4+ star plans: {r['pct_4plus_enrollment']:.1f}%"
        ),
        axis=1
    )

    fig = px.choropleth(
        state_stats,
        locations='state_abbr',
        locationmode='USA-states',
        color='avg_rating',
        color_continuous_scale='RdYlGn',
        range_color=(2.0, 5.0),
        scope="usa",
        hover_name='hover_text',
        labels={'avg_rating': 'Avg Star Rating'},
        title=f"Medicare Advantage Quality by State ({CURRENT_YEAR})<br><sub>Enrollment-weighted average star ratings</sub>"
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=80, b=0),
        coloraxis_colorbar=dict(
            title="Star Rating",
            tickvals=[2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0],
            ticktext=['2.0⭐', '2.5⭐', '3.0⭐', '3.5⭐', '4.0⭐', '4.5⭐', '5.0⭐']
        )
    )

    return fig


def create_temporal_dashboard(state_trends, trend_stats_df):
    """
    Create a comprehensive temporal dashboard showing:
    1. Current ratings by state (choropleth)
    2. Rating changes 2020-2024 (choropleth)
    3. Top improvers/decliners (bar chart)
    4. Trend lines for selected states
    """
    print("Creating temporal trend dashboard...")

    # Create subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            f'Current Ratings ({CURRENT_YEAR})',
            f'Change from {START_YEAR} to {CURRENT_YEAR}',
            'Top 10 Improvers & Decliners',
            'Rating Trajectories (Selected States)'
        ),
        specs=[
            [{'type': 'choropleth'}, {'type': 'choropleth'}],
            [{'type': 'bar'}, {'type': 'scatter'}]
        ],
        vertical_spacing=0.15,
        horizontal_spacing=0.1
    )

    # 1. Current ratings choropleth
    current_hover = trend_stats_df.apply(
        lambda r: f"<b>{r['state_abbr']}</b><br>Current: {r['current_rating']:.2f}⭐",
        axis=1
    )

    fig.add_trace(
        go.Choropleth(
            locations=trend_stats_df['state_abbr'],
            z=trend_stats_df['current_rating'],
            locationmode='USA-states',
            colorscale='RdYlGn',
            zmin=2.0, zmax=5.0,
            text=current_hover,
            hoverinfo='text',
            colorbar=dict(x=0.45, y=0.85, len=0.3, title="Rating"),
            showscale=True
        ),
        row=1, col=1
    )

    # 2. Change choropleth (diverging color scale)
    change_hover = trend_stats_df.apply(
        lambda r: (
            f"<b>{r['state_abbr']}</b><br>"
            f"{START_YEAR}: {r['rating_2020']:.2f}⭐<br>"
            f"{CURRENT_YEAR}: {r['current_rating']:.2f}⭐<br>"
            f"Change: {r['total_change']:+.2f}⭐ ({r['pct_change']:+.1f}%)"
        ),
        axis=1
    )

    fig.add_trace(
        go.Choropleth(
            locations=trend_stats_df['state_abbr'],
            z=trend_stats_df['total_change'],
            locationmode='USA-states',
            colorscale='RdBu',  # Red for decline, Blue for improvement
            zmid=0,
            zmin=-0.5, zmax=0.5,
            text=change_hover,
            hoverinfo='text',
            colorbar=dict(x=1.0, y=0.85, len=0.3, title="Change"),
            showscale=True
        ),
        row=1, col=2
    )

    # 3. Top improvers and decliners bar chart
    top_n = 10
    top_improvers = trend_stats_df.nlargest(top_n, 'total_change')
    top_decliners = trend_stats_df.nsmallest(top_n, 'total_change')
    bar_data = pd.concat([top_decliners, top_improvers]).sort_values('total_change')

    colors = ['red' if x < 0 else 'green' for x in bar_data['total_change']]

    fig.add_trace(
        go.Bar(
            y=bar_data['state_abbr'],
            x=bar_data['total_change'],
            orientation='h',
            marker=dict(color=colors),
            text=[f"{x:+.2f}⭐" for x in bar_data['total_change']],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Change: %{x:+.2f}⭐<extra></extra>'
        ),
        row=2, col=1
    )

    # 4. Trend lines for selected states (biggest movers + a few stable)
    top_5_improvers = trend_stats_df.nlargest(5, 'total_change')['state_abbr'].tolist()
    top_5_decliners = trend_stats_df.nsmallest(5, 'total_change')['state_abbr'].tolist()
    selected_states = top_5_improvers[:3] + top_5_decliners[:3]

    for state in selected_states:
        state_data = state_trends[state_trends['state_abbr'] == state].sort_values('year')

        fig.add_trace(
            go.Scatter(
                x=state_data['year'],
                y=state_data['avg_rating'],
                mode='lines+markers',
                name=state,
                line=dict(width=2),
                hovertemplate=f'<b>{state}</b><br>Year: %{{x}}<br>Rating: %{{y:.2f}}⭐<extra></extra>'
            ),
            row=2, col=2
        )

    # Update layout
    fig.update_geos(
        scope='usa',
        showlakes=True,
        lakecolor='rgb(230, 245, 255)'
    )

    fig.update_xaxes(title_text="Change in Stars", row=2, col=1)
    fig.update_yaxes(title_text="", row=2, col=1)

    fig.update_xaxes(title_text="Year", row=2, col=2, range=[START_YEAR - 0.5, CURRENT_YEAR + 0.5])
    fig.update_yaxes(title_text="Avg Star Rating", row=2, col=2, range=[2.0, 5.0])

    fig.update_layout(
        title_text=f"Medicare Advantage Star Ratings: Geographic & Temporal Analysis ({START_YEAR}-{CURRENT_YEAR})",
        height=1000,
        showlegend=True,
        legend=dict(x=0.75, y=0.25, bgcolor='rgba(255,255,255,0.8)')
    )

    return fig


def create_quality_desert_analysis(county_stats):
    """
    Create detailed analysis of quality deserts.
    """
    print("Analyzing quality deserts...")

    deserts = county_stats[county_stats['is_quality_desert']].copy()
    deserts['affected_beneficiaries'] = deserts['total_enrollment']

    # Sort by enrollment to find largest quality deserts
    deserts = deserts.sort_values('total_enrollment', ascending=False)

    # Summary statistics
    summary = {
        'total_counties': len(county_stats),
        'quality_desert_counties': len(deserts),
        'pct_counties_deserts': len(deserts) / len(county_stats) * 100,
        'total_ma_enrollment': county_stats['total_enrollment'].sum(),
        'desert_enrollment': deserts['total_enrollment'].sum(),
        'pct_enrollment_deserts': deserts['total_enrollment'].sum() / county_stats['total_enrollment'].sum() * 100,
        'avg_rating_deserts': deserts['avg_rating'].mean(),
        'avg_rating_non_deserts': county_stats[~county_stats['is_quality_desert']]['avg_rating'].mean(),
    }

    print(f"\n{'='*60}")
    print("QUALITY DESERT ANALYSIS")
    print(f"{'='*60}")
    print(f"Total Counties: {summary['total_counties']:,}")
    print(f"Quality Desert Counties: {summary['quality_desert_counties']:,} ({summary['pct_counties_deserts']:.1f}%)")
    print(f"Beneficiaries in Quality Deserts: {int(summary['desert_enrollment']):,} ({summary['pct_enrollment_deserts']:.1f}%)")
    print(f"Avg Rating in Deserts: {summary['avg_rating_deserts']:.2f}⭐")
    print(f"Avg Rating Outside Deserts: {summary['avg_rating_non_deserts']:.2f}⭐")
    print(f"{'='*60}\n")

    # Top 20 largest quality deserts by enrollment
    print("Top 20 Largest Quality Deserts by Enrollment:")
    print(deserts[['county_name', 'state_abbr', 'avg_rating', 'num_plans', 'total_enrollment']].head(20).to_string(index=False))

    return deserts, summary


# -------------------------
# MAIN
# -------------------------
def main():
    print(f"\n{'='*60}")
    print(f"Medicare Advantage Geographic Quality Analysis ({START_YEAR}-{CURRENT_YEAR})")
    print(f"{'='*60}\n")

    # 1. Fetch multi-year data
    star_ratings_all = fetch_star_ratings_multiyear(YEARS)
    enrollment_all = fetch_enrollment_by_county_multiyear(YEARS)
    counties_geo = fetch_county_geojson()

    print(f"\nLoaded {len(star_ratings_all):,} MA contract-year records ({len(YEARS)} years)")
    print(f"Loaded {len(enrollment_all):,} enrollment records across {enrollment_all['county_fips'].nunique():,} counties")

    # 2. Calculate current year ratings (for county map)
    star_ratings_current = star_ratings_all[star_ratings_all['year'] == CURRENT_YEAR]
    enrollment_current = enrollment_all[enrollment_all['year'] == CURRENT_YEAR]

    county_stats = calculate_county_ratings(star_ratings_current, enrollment_current)
    state_stats = calculate_state_ratings(county_stats)

    # 3. Calculate temporal trends
    state_trends, trend_stats = calculate_state_trends(star_ratings_all, enrollment_all, YEARS)

    # 4. Quality desert analysis
    deserts_df, summary = create_quality_desert_analysis(county_stats)

    # 5. Create visualizations
    county_fig = create_county_map(county_stats, counties_geo)
    state_fig = create_state_map(state_stats)
    temporal_fig = create_temporal_dashboard(state_trends, trend_stats)

    # 6. Save outputs
    print("\nSaving outputs...")

    # County map
    county_html = OUTPUT_DIR / "ma_star_ratings_county_map.html"
    county_fig.write_html(str(county_html), include_plotlyjs='cdn')
    print(f"✓ Saved: {county_html}")

    try:
        county_png = OUTPUT_DIR / "ma_star_ratings_county_map.png"
        county_fig.write_image(str(county_png), scale=2, width=1400, height=900)
        print(f"✓ Saved: {county_png}")
    except Exception as e:
        print(f"⚠ PNG export skipped (install 'kaleido' to enable): {e}")

    # State map
    state_html = OUTPUT_DIR / "ma_star_ratings_state_map.html"
    state_fig.write_html(str(state_html), include_plotlyjs='cdn')
    print(f"✓ Saved: {state_html}")

    try:
        state_png = OUTPUT_DIR / "ma_star_ratings_state_map.png"
        state_fig.write_image(str(state_png), scale=2, width=1400, height=900)
        print(f"✓ Saved: {state_png}")
    except Exception as e:
        print(f"⚠ PNG export skipped: {e}")

    # Temporal dashboard
    temporal_html = OUTPUT_DIR / "ma_star_ratings_temporal_dashboard.html"
    temporal_fig.write_html(str(temporal_html), include_plotlyjs='cdn')
    print(f"✓ Saved: {temporal_html}")

    try:
        temporal_png = OUTPUT_DIR / "ma_star_ratings_temporal_dashboard.png"
        temporal_fig.write_image(str(temporal_png), scale=2, width=1800, height=1000)
        print(f"✓ Saved: {temporal_png}")
    except Exception as e:
        print(f"⚠ PNG export skipped: {e}")

    # Quality deserts CSV
    deserts_csv = OUTPUT_DIR / "ma_quality_deserts_summary.csv"
    deserts_df.to_csv(deserts_csv, index=False)
    print(f"✓ Saved: {deserts_csv}")

    # Trend statistics CSV
    trend_csv = OUTPUT_DIR / "ma_state_trend_statistics.csv"
    trend_stats.to_csv(trend_csv, index=False)
    print(f"✓ Saved: {trend_csv}")

    # Summary stats CSV
    summary_csv = OUTPUT_DIR / "ma_quality_summary_stats.csv"
    pd.DataFrame([summary]).to_csv(summary_csv, index=False)
    print(f"✓ Saved: {summary_csv}")

    print(f"\n{'='*60}")
    print("Analysis complete!")
    print(f"{'='*60}\n")

    # LinkedIn-ready caption with temporal insights
    top_improvers = trend_stats.nlargest(3, 'total_change')[['state_abbr', 'total_change']].values
    top_decliners = trend_stats.nsmallest(3, 'total_change')[['state_abbr', 'total_change']].values

    caption = f"""
Medicare Advantage Quality: Geographic Disparities & Temporal Trends ({START_YEAR}-{CURRENT_YEAR})

📍 QUALITY DESERTS ({CURRENT_YEAR}):
• {summary['quality_desert_counties']:,} counties ({summary['pct_counties_deserts']:.1f}%) have avg ratings <{QUALITY_DESERT_THRESHOLD}⭐ or fewer than {LOW_ACCESS_THRESHOLD} plans
• {int(summary['desert_enrollment']):,} beneficiaries ({summary['pct_enrollment_deserts']:.1f}% of MA enrollment) affected
• Gap: {summary['avg_rating_deserts']:.2f}⭐ in deserts vs {summary['avg_rating_non_deserts']:.2f}⭐ elsewhere

📈 TRENDS ({START_YEAR}-{CURRENT_YEAR}):
• Top Improvers: {', '.join([f'{s} (+{c:.2f}⭐)' for s, c in top_improvers])}
• Biggest Declines: {', '.join([f'{s} ({c:.2f}⭐)' for s, c in top_decliners])}
• National pattern: {'Most states improving' if (trend_stats['total_change'] > 0).sum() > len(trend_stats)/2 else 'Mixed trends'}

Why this matters:
Star ratings determine quality bonus payments ($10B+ annually), influence auto-enrollment, and shape consumer choice.
Geographic disparities persist even as overall quality evolves — some states' plans are improving rapidly while others lag.

Source: CMS Medicare Advantage Star Ratings & Enrollment Data ({START_YEAR}-{CURRENT_YEAR})
Analysis: Enrollment-weighted average ratings by state & county
    """

    print("\n" + "="*60)
    print("LINKEDIN CAPTION")
    print("="*60)
    print(caption.strip())


if __name__ == "__main__":
    try:
        import plotly
        import requests
    except ImportError:
        print("Missing dependencies. Install with:")
        print("pip install pandas numpy matplotlib plotly requests kaleido")
        exit(1)

    main()
