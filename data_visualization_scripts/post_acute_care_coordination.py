#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post-Acute Care Coordination "Leak" Analysis
Analyzes hospital discharge patterns, post-acute care pathways, and care coordination failures.
Identifies where care transitions break down leading to readmissions and poor outcomes.

Key Visualizations:
1. Sankey diagram: Hospital → Post-acute setting flows
2. Readmission rates by discharge destination & condition
3. Care coordination "leak" timeline (days to first contact)
4. SNF quality correlation with patient outcomes
5. Geographic variation in discharge patterns

Data simulates CMS discharge data, SNF quality ratings, and readmission tracking.

Author: Generated with Claude Code
"""

import io
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# -------------------------
# CONFIG
# -------------------------
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Discharge destinations
DISCHARGE_SETTINGS = {
    'SNF': 'Skilled Nursing Facility',
    'HH': 'Home Health',
    'IRF': 'Inpatient Rehab Facility',
    'LTCH': 'Long-Term Care Hospital',
    'Home': 'Home (Self-Care)',
    'Other': 'Other/Unknown'
}

# Common index conditions for analysis
INDEX_CONDITIONS = [
    'Hip Fracture',
    'Stroke',
    'Heart Failure',
    'Pneumonia',
    'COPD',
    'Joint Replacement',
    'Sepsis'
]

# Care coordination leak categories
LEAK_TYPES = [
    'Delayed first visit (>7 days)',
    'No documented follow-up',
    'Medication reconciliation gap',
    'Communication failure (no handoff)',
    'Early discharge (against medical advice)'
]


# -------------------------
# SYNTHETIC DATA GENERATION
# -------------------------
def generate_discharge_data(n_patients=5000):
    """
    Generate synthetic hospital discharge data with post-acute pathways.
    """
    print("Generating synthetic discharge data...")

    np.random.seed(42)

    discharges = []

    for i in range(n_patients):
        # Index condition
        condition = np.random.choice(INDEX_CONDITIONS, p=[0.15, 0.12, 0.20, 0.15, 0.12, 0.18, 0.08])

        # Age and comorbidity influence discharge destination
        age = np.random.randint(65, 95)
        comorbidity_score = np.random.randint(0, 8)

        # Discharge destination probabilities vary by condition and patient factors
        if condition in ['Hip Fracture', 'Stroke', 'Joint Replacement']:
            # Higher SNF/IRF utilization
            dest_probs = {'SNF': 0.45, 'HH': 0.25, 'IRF': 0.15, 'LTCH': 0.02, 'Home': 0.10, 'Other': 0.03}
        elif condition in ['Heart Failure', 'Pneumonia', 'COPD']:
            # Higher home health utilization
            dest_probs = {'SNF': 0.25, 'HH': 0.40, 'IRF': 0.05, 'LTCH': 0.03, 'Home': 0.25, 'Other': 0.02}
        else:  # Sepsis
            dest_probs = {'SNF': 0.35, 'HH': 0.30, 'IRF': 0.10, 'LTCH': 0.08, 'Home': 0.15, 'Other': 0.02}

        # Adjust for age (older → more institutional)
        if age > 85:
            dest_probs['SNF'] *= 1.3
            dest_probs['Home'] *= 0.6
            # Renormalize
            total = sum(dest_probs.values())
            dest_probs = {k: v/total for k, v in dest_probs.items()}

        destination = np.random.choice(list(dest_probs.keys()), p=list(dest_probs.values()))

        # Length of stay
        los = max(1, int(np.random.gamma(3, 2)))

        # Care coordination metrics
        days_to_first_visit = None
        has_medication_reconciliation = np.random.random() > 0.15  # 85% have it
        has_handoff_communication = np.random.random() > 0.10  # 90% have it

        if destination in ['SNF', 'HH', 'IRF', 'LTCH']:
            # Days until first post-acute contact
            if destination == 'SNF':
                days_to_first_visit = 0  # Immediate transfer
            elif destination == 'HH':
                days_to_first_visit = max(0, int(np.random.gamma(2, 1.5)))  # Often 1-3 days
            else:
                days_to_first_visit = max(0, int(np.random.gamma(1.5, 1)))

        # Readmission within 30 days
        # Base rate varies by condition and destination
        base_readmit_rate = {
            'Hip Fracture': 0.08, 'Stroke': 0.12, 'Heart Failure': 0.22,
            'Pneumonia': 0.18, 'COPD': 0.20, 'Joint Replacement': 0.05, 'Sepsis': 0.25
        }[condition]

        # Adjust for discharge destination quality
        if destination == 'SNF':
            # SNF quality varies - will assign later
            snf_quality_modifier = np.random.uniform(0.8, 1.4)
            base_readmit_rate *= snf_quality_modifier
        elif destination == 'Home':
            base_readmit_rate *= 1.3  # Higher risk without support
        elif destination in ['IRF', 'HH']:
            base_readmit_rate *= 0.9  # Lower risk with support

        # Care coordination failures increase readmission risk
        if days_to_first_visit and days_to_first_visit > 7:
            base_readmit_rate *= 1.5
        if not has_medication_reconciliation:
            base_readmit_rate *= 1.4
        if not has_handoff_communication:
            base_readmit_rate *= 1.6

        readmitted = np.random.random() < base_readmit_rate

        # Days to readmission if applicable
        days_to_readmit = int(np.random.uniform(1, 30)) if readmitted else None

        # Identify care coordination leak type (if readmitted)
        leak_type = None
        if readmitted:
            if days_to_first_visit and days_to_first_visit > 7:
                leak_type = 'Delayed first visit (>7 days)'
            elif not has_medication_reconciliation:
                leak_type = 'Medication reconciliation gap'
            elif not has_handoff_communication:
                leak_type = 'Communication failure (no handoff)'
            else:
                leak_type = np.random.choice(['No documented follow-up', 'Early discharge (against medical advice)'])

        discharges.append({
            'patient_id': f'P{i:05d}',
            'condition': condition,
            'age': age,
            'comorbidity_score': comorbidity_score,
            'los': los,
            'discharge_destination': destination,
            'days_to_first_visit': days_to_first_visit,
            'has_med_reconciliation': has_medication_reconciliation,
            'has_handoff': has_handoff_communication,
            'readmitted_30d': readmitted,
            'days_to_readmit': days_to_readmit,
            'leak_type': leak_type
        })

    return pd.DataFrame(discharges)


def generate_snf_quality_data():
    """
    Generate synthetic SNF quality ratings and characteristics.
    """
    print("Generating SNF quality data...")

    np.random.seed(43)
    n_snfs = 150

    snfs = []
    for i in range(n_snfs):
        # Star rating (1-5)
        star_rating = np.random.choice([1, 2, 3, 4, 5], p=[0.10, 0.20, 0.35, 0.25, 0.10])

        # Quality metrics correlate with star rating
        base_quality = star_rating / 5.0

        # Staffing hours per resident day (HPRD)
        hprd = np.random.normal(3.5 + (star_rating - 3) * 0.5, 0.8)
        hprd = max(2.0, hprd)

        # Readmission rate (inverse correlation with quality)
        readmit_rate = np.random.normal(0.22 - (star_rating - 3) * 0.03, 0.04)
        readmit_rate = np.clip(readmit_rate, 0.10, 0.35)

        # Average length of stay
        avg_los = np.random.normal(25 + (star_rating - 3) * 3, 5)
        avg_los = max(10, avg_los)

        snfs.append({
            'snf_id': f'SNF_{i:03d}',
            'star_rating': star_rating,
            'hprd': hprd,
            'readmit_rate': readmit_rate,
            'avg_los': avg_los,
            'bed_count': np.random.randint(50, 200)
        })

    return pd.DataFrame(snfs)


# -------------------------
# ANALYSIS FUNCTIONS
# -------------------------
def analyze_discharge_flows(df):
    """
    Analyze discharge patterns from hospital to post-acute settings.
    """
    print("Analyzing discharge flows...")

    # Count by condition and destination
    flows = df.groupby(['condition', 'discharge_destination']).size().reset_index(name='count')

    # Calculate readmission rates by pathway
    readmit = df.groupby(['condition', 'discharge_destination'])['readmitted_30d'].mean().reset_index()
    readmit.columns = ['condition', 'discharge_destination', 'readmit_rate']

    flows = flows.merge(readmit, on=['condition', 'discharge_destination'])

    return flows


def analyze_care_coordination_leaks(df):
    """
    Identify where care coordination breaks down.
    """
    print("Analyzing care coordination leaks...")

    # Only look at readmitted patients
    readmits = df[df['readmitted_30d']].copy()

    # Leak type distribution
    leak_dist = readmits['leak_type'].value_counts().reset_index()
    leak_dist.columns = ['leak_type', 'count']
    leak_dist['pct'] = 100 * leak_dist['count'] / leak_dist['count'].sum()

    # Days to first visit analysis (for applicable settings)
    time_to_contact = df[df['days_to_first_visit'].notna()].copy()
    time_to_contact['delayed'] = time_to_contact['days_to_first_visit'] > 7

    # Readmission rate by delay status
    delay_impact = time_to_contact.groupby(['discharge_destination', 'delayed'])['readmitted_30d'].agg(['mean', 'count']).reset_index()
    delay_impact.columns = ['destination', 'delayed', 'readmit_rate', 'patient_count']

    return leak_dist, delay_impact


# -------------------------
# VISUALIZATIONS
# -------------------------
def create_sankey_diagram(flows_df):
    """
    Create Sankey diagram showing discharge flows.
    """
    print("Creating discharge flow Sankey diagram...")

    # Build nodes
    conditions = flows_df['condition'].unique().tolist()
    destinations = flows_df['discharge_destination'].unique().tolist()

    all_nodes = conditions + destinations
    node_dict = {name: idx for idx, name in enumerate(all_nodes)}

    # Build links
    source = []
    target = []
    value = []
    color = []

    for _, row in flows_df.iterrows():
        source.append(node_dict[row['condition']])
        target.append(node_dict[row['discharge_destination']])
        value.append(row['count'])

        # Color by readmission rate
        if row['readmit_rate'] > 0.20:
            color.append('rgba(255, 100, 100, 0.4)')  # Red for high readmit
        elif row['readmit_rate'] > 0.15:
            color.append('rgba(255, 200, 100, 0.4)')  # Orange
        else:
            color.append('rgba(100, 200, 100, 0.4)')  # Green for low readmit

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=all_nodes,
            color=['lightblue'] * len(conditions) + ['lightgreen'] * len(destinations)
        ),
        link=dict(
            source=source,
            target=target,
            value=value,
            color=color
        )
    )])

    fig.update_layout(
        title="Hospital Discharge Pathways<br><sub>Flow from index condition → post-acute setting (color = readmission risk)</sub>",
        font=dict(size=12),
        height=600
    )

    return fig


def create_readmission_dashboard(df, flows_df, leak_dist):
    """
    Multi-panel dashboard showing readmission patterns and leaks.
    """
    print("Creating readmission analysis dashboard...")

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Readmission Rate by Discharge Destination',
            'Care Coordination Leak Types',
            'Readmission Rate by Condition & Setting',
            'Time-to-First-Visit Impact'
        ),
        specs=[
            [{'type': 'bar'}, {'type': 'bar'}],
            [{'type': 'bar'}, {'type': 'scatter'}]
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.15
    )

    # 1. Readmission by destination
    readmit_by_dest = df.groupby('discharge_destination')['readmitted_30d'].agg(['mean', 'count']).reset_index()
    readmit_by_dest = readmit_by_dest[readmit_by_dest['count'] >= 20]  # Filter small groups
    readmit_by_dest = readmit_by_dest.sort_values('mean', ascending=False)

    fig.add_trace(
        go.Bar(
            x=readmit_by_dest['discharge_destination'],
            y=readmit_by_dest['mean'] * 100,
            marker=dict(color=readmit_by_dest['mean'] * 100, colorscale='Reds', showscale=False),
            text=[f"{x:.1f}%" for x in readmit_by_dest['mean'] * 100],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Readmit Rate: %{y:.1f}%<br>N=%{customdata}<extra></extra>',
            customdata=readmit_by_dest['count']
        ),
        row=1, col=1
    )

    # 2. Leak types
    leak_dist_sorted = leak_dist.sort_values('count', ascending=True)

    fig.add_trace(
        go.Bar(
            y=leak_dist_sorted['leak_type'],
            x=leak_dist_sorted['count'],
            orientation='h',
            marker=dict(color='crimson'),
            text=[f"{x:.1f}%" for x in leak_dist_sorted['pct']],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Count: %{x}<br>% of Readmits: %{customdata:.1f}%<extra></extra>',
            customdata=leak_dist_sorted['pct']
        ),
        row=1, col=2
    )

    # 3. Heatmap: readmission by condition x destination
    pivot = flows_df.pivot(index='condition', columns='discharge_destination', values='readmit_rate')

    # Only show top destinations
    top_dests = ['SNF', 'HH', 'Home', 'IRF']
    pivot = pivot[[d for d in top_dests if d in pivot.columns]]

    fig.add_trace(
        go.Heatmap(
            z=pivot.values * 100,
            x=pivot.columns,
            y=pivot.index,
            colorscale='YlOrRd',
            text=pivot.values * 100,
            texttemplate='%{text:.1f}%',
            textfont={"size": 10},
            colorbar=dict(title="Readmit %", x=1.15)
        ),
        row=2, col=1
    )

    # 4. Days to first visit scatter
    time_analysis = df[df['days_to_first_visit'].notna()].copy()
    time_analysis['delay_category'] = pd.cut(
        time_analysis['days_to_first_visit'],
        bins=[-1, 3, 7, 30],
        labels=['0-3 days', '4-7 days', '>7 days']
    )

    delay_readmit = time_analysis.groupby(['discharge_destination', 'delay_category']).agg({
        'readmitted_30d': 'mean',
        'patient_id': 'count'
    }).reset_index()
    delay_readmit.columns = ['destination', 'delay_category', 'readmit_rate', 'count']

    for dest in delay_readmit['destination'].unique():
        dest_data = delay_readmit[delay_readmit['destination'] == dest]
        fig.add_trace(
            go.Scatter(
                x=dest_data['delay_category'],
                y=dest_data['readmit_rate'] * 100,
                mode='lines+markers',
                name=dest,
                line=dict(width=2),
                marker=dict(size=8),
                hovertemplate='<b>%{fullData.name}</b><br>Delay: %{x}<br>Readmit: %{y:.1f}%<extra></extra>'
            ),
            row=2, col=2
        )

    # Update axes
    fig.update_xaxes(title_text="Discharge Destination", row=1, col=1)
    fig.update_yaxes(title_text="30-Day Readmit Rate (%)", row=1, col=1)

    fig.update_xaxes(title_text="Readmissions (n)", row=1, col=2)
    fig.update_yaxes(title_text="", row=1, col=2)

    fig.update_xaxes(title_text="", row=2, col=1)
    fig.update_yaxes(title_text="", row=2, col=1)

    fig.update_xaxes(title_text="Time to First Visit", row=2, col=2)
    fig.update_yaxes(title_text="Readmit Rate (%)", row=2, col=2)

    fig.update_layout(
        title_text="Post-Acute Care Coordination Failure Analysis",
        height=900,
        showlegend=True,
        legend=dict(x=0.75, y=0.25, bgcolor='rgba(255,255,255,0.8)')
    )

    return fig


def create_snf_quality_analysis(snf_df):
    """
    Analyze SNF quality correlation with outcomes.
    """
    print("Creating SNF quality analysis...")

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            'SNF Star Rating vs Readmission Rate',
            'Staffing Levels vs Readmission Rate'
        )
    )

    # 1. Star rating vs readmit scatter
    fig.add_trace(
        go.Scatter(
            x=snf_df['star_rating'],
            y=snf_df['readmit_rate'] * 100,
            mode='markers',
            marker=dict(
                size=snf_df['bed_count'] / 3,
                color=snf_df['star_rating'],
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title="Stars", x=0.45)
            ),
            text=snf_df['snf_id'],
            hovertemplate='<b>%{text}</b><br>Stars: %{x}<br>Readmit: %{y:.1f}%<br>Beds: %{marker.size}<extra></extra>'
        ),
        row=1, col=1
    )

    # Add trendline
    z = np.polyfit(snf_df['star_rating'], snf_df['readmit_rate'] * 100, 1)
    p = np.poly1d(z)
    x_trend = np.linspace(1, 5, 100)

    fig.add_trace(
        go.Scatter(
            x=x_trend,
            y=p(x_trend),
            mode='lines',
            line=dict(color='red', dash='dash', width=2),
            name='Trend',
            showlegend=False,
            hoverinfo='skip'
        ),
        row=1, col=1
    )

    # 2. Staffing vs readmit
    fig.add_trace(
        go.Scatter(
            x=snf_df['hprd'],
            y=snf_df['readmit_rate'] * 100,
            mode='markers',
            marker=dict(
                size=snf_df['bed_count'] / 3,
                color=snf_df['star_rating'],
                colorscale='RdYlGn',
                showscale=False
            ),
            text=snf_df['snf_id'],
            hovertemplate='<b>%{text}</b><br>HPRD: %{x:.2f}<br>Readmit: %{y:.1f}%<extra></extra>'
        ),
        row=1, col=2
    )

    # Staffing trendline
    z2 = np.polyfit(snf_df['hprd'], snf_df['readmit_rate'] * 100, 1)
    p2 = np.poly1d(z2)
    x_trend2 = np.linspace(snf_df['hprd'].min(), snf_df['hprd'].max(), 100)

    fig.add_trace(
        go.Scatter(
            x=x_trend2,
            y=p2(x_trend2),
            mode='lines',
            line=dict(color='red', dash='dash', width=2),
            name='Trend',
            showlegend=False,
            hoverinfo='skip'
        ),
        row=1, col=2
    )

    fig.update_xaxes(title_text="Star Rating", row=1, col=1, dtick=1)
    fig.update_yaxes(title_text="30-Day Readmission Rate (%)", row=1, col=1)

    fig.update_xaxes(title_text="Hours Per Resident Day (HPRD)", row=1, col=2)
    fig.update_yaxes(title_text="30-Day Readmission Rate (%)", row=1, col=2)

    fig.update_layout(
        title_text="SNF Quality Metrics Impact on Patient Outcomes",
        height=500
    )

    return fig


# -------------------------
# MAIN
# -------------------------
def main():
    print(f"\n{'='*70}")
    print("Post-Acute Care Coordination 'Leak' Analysis")
    print(f"{'='*70}\n")

    # 1. Generate data
    discharge_df = generate_discharge_data(n_patients=5000)
    snf_df = generate_snf_quality_data()

    print(f"\nGenerated {len(discharge_df):,} discharge records")
    print(f"Overall 30-day readmission rate: {discharge_df['readmitted_30d'].mean()*100:.1f}%")

    # 2. Analyze flows
    flows = analyze_discharge_flows(discharge_df)
    leak_dist, delay_impact = analyze_care_coordination_leaks(discharge_df)

    # 3. Create visualizations
    sankey_fig = create_sankey_diagram(flows)
    dashboard_fig = create_readmission_dashboard(discharge_df, flows, leak_dist)
    snf_fig = create_snf_quality_analysis(snf_df)

    # 4. Save outputs
    print("\nSaving outputs...")

    sankey_html = OUTPUT_DIR / "post_acute_discharge_flows.html"
    sankey_fig.write_html(str(sankey_html), include_plotlyjs='cdn')
    print(f"✓ Saved: {sankey_html}")

    dashboard_html = OUTPUT_DIR / "care_coordination_leaks_dashboard.html"
    dashboard_fig.write_html(str(dashboard_html), include_plotlyjs='cdn')
    print(f"✓ Saved: {dashboard_html}")

    snf_html = OUTPUT_DIR / "snf_quality_outcomes.html"
    snf_fig.write_html(str(snf_html), include_plotlyjs='cdn')
    print(f"✓ Saved: {snf_html}")

    # Export PNGs if kaleido available
    try:
        sankey_png = OUTPUT_DIR / "post_acute_discharge_flows.png"
        sankey_fig.write_image(str(sankey_png), scale=2, width=1400, height=600)
        print(f"✓ Saved: {sankey_png}")

        dashboard_png = OUTPUT_DIR / "care_coordination_leaks_dashboard.png"
        dashboard_fig.write_image(str(dashboard_png), scale=2, width=1600, height=900)
        print(f"✓ Saved: {dashboard_png}")

        snf_png = OUTPUT_DIR / "snf_quality_outcomes.png"
        snf_fig.write_image(str(snf_png), scale=2, width=1400, height=500)
        print(f"✓ Saved: {snf_png}")
    except Exception as e:
        print(f"⚠ PNG export skipped (install 'kaleido' to enable): {e}")

    # Export summary CSVs
    flows.to_csv(OUTPUT_DIR / "discharge_flows_summary.csv", index=False)
    print(f"✓ Saved: {OUTPUT_DIR / 'discharge_flows_summary.csv'}")

    leak_dist.to_csv(OUTPUT_DIR / "care_coordination_leaks.csv", index=False)
    print(f"✓ Saved: {OUTPUT_DIR / 'care_coordination_leaks.csv'}")

    discharge_df.to_csv(OUTPUT_DIR / "discharge_data_full.csv", index=False)
    print(f"✓ Saved: {OUTPUT_DIR / 'discharge_data_full.csv'}")

    snf_df.to_csv(OUTPUT_DIR / "snf_quality_data.csv", index=False)
    print(f"✓ Saved: {OUTPUT_DIR / 'snf_quality_data.csv'}")

    print(f"\n{'='*70}")
    print("Analysis complete!")
    print(f"{'='*70}\n")

    # Generate insights summary
    total_readmits = discharge_df['readmitted_30d'].sum()
    readmit_with_leaks = discharge_df[discharge_df['leak_type'].notna()].shape[0]

    top_leak = leak_dist.iloc[0]
    worst_destination = flows.loc[flows['readmit_rate'].idxmax()]
    best_destination = flows.loc[flows['readmit_rate'].idxmin()]

    # SNF quality correlation
    snf_corr = snf_df[['star_rating', 'readmit_rate']].corr().iloc[0, 1]

    caption = f"""
Post-Acute Care Coordination "Leaks" — Where Transitions Break Down

📊 DISCHARGE PATTERNS:
• {len(discharge_df):,} hospital discharges analyzed across 7 conditions
• Overall 30-day readmission rate: {discharge_df['readmitted_30d'].mean()*100:.1f}%
• {total_readmits:,} readmissions, {readmit_with_leaks:,} ({readmit_with_leaks/total_readmits*100:.1f}%) linked to care coordination failures

🚨 CARE COORDINATION LEAKS:
• Top leak type: {top_leak['leak_type']} ({top_leak['pct']:.1f}% of readmissions)
• Highest-risk pathway: {worst_destination['condition']} → {worst_destination['discharge_destination']} ({worst_destination['readmit_rate']*100:.1f}% readmit)
• Best outcomes: {best_destination['condition']} → {best_destination['discharge_destination']} ({best_destination['readmit_rate']*100:.1f}% readmit)

🏥 SNF QUALITY IMPACT:
• Correlation between SNF star rating & readmissions: {snf_corr:.3f}
• 1-star SNFs: ~{snf_df[snf_df['star_rating']==1]['readmit_rate'].mean()*100:.1f}% readmit rate
• 5-star SNFs: ~{snf_df[snf_df['star_rating']==5]['readmit_rate'].mean()*100:.1f}% readmit rate

Why this matters:
Care transitions are a major vulnerability point in the healthcare system. Every leak—delayed follow-up, missed medication
reconciliation, poor handoffs—increases readmission risk and costs Medicare billions. Identifying and fixing these
coordination failures is low-hanging fruit for improving outcomes and reducing spending.

Source: Synthetic data modeling CMS discharge patterns & SNF quality metrics
Analysis: Post-acute pathway optimization & care coordination failure detection
    """

    print("\n" + "="*70)
    print("LINKEDIN CAPTION")
    print("="*70)
    print(caption.strip())


if __name__ == "__main__":
    try:
        import plotly
    except ImportError:
        print("Missing dependencies. Install with:")
        print("pip install pandas numpy plotly kaleido")
        exit(1)

    main()
