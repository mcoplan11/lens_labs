"""
SNF Comparison Dashboard
Interactive dashboard for comparing Skilled Nursing Facilities using CMS data
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from cms_api import CMSAPI

# Page configuration
st.set_page_config(
    page_title="Compare SNF | Skilled Nursing Facility Comparison Tool - CMS Quality Ratings",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://data.cms.gov/provider-data',
        'Report a bug': None,
        'About': "Compare skilled nursing facilities using official CMS quality ratings. Free SNF comparison tool with star ratings, quality measures, and facility data."
    }
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #0066CC;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        text-align: center;
        color: #6C757D;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #F8F9FA;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #0066CC;
    }
    .stButton>button {
        width: 100%;
    }
    .rating-5 { color: #28A745; }
    .rating-4 { color: #90C351; }
    .rating-3 { color: #FFC107; }
    .rating-2 { color: #FF8C42; }
    .rating-1 { color: #DC3545; }
</style>
""", unsafe_allow_html=True)

# Initialize API
@st.cache_resource
def get_api():
    return CMSAPI()

api = get_api()

# Initialize session state
if 'facilities_df' not in st.session_state:
    st.session_state.facilities_df = api._get_sample_data()
if 'selected_for_comparison' not in st.session_state:
    st.session_state.selected_for_comparison = []

# Helper functions
def render_stars(rating):
    """Render star rating"""
    if rating == 0:
        return "☆☆☆☆☆ (Not Rated)"
    filled = "★" * rating
    empty = "☆" * (5 - rating)
    return f"{filled}{empty} ({rating})"

def get_rating_color(rating):
    """Get color based on rating"""
    colors = {5: "#28A745", 4: "#90C351", 3: "#FFC107", 2: "#FF8C42", 1: "#DC3545", 0: "#6C757D"}
    return colors.get(rating, "#6C757D")

def filter_dataframe(df, filters):
    """Apply filters to dataframe"""
    filtered_df = df.copy()

    # Rating filter
    if filters['ratings']:
        filtered_df = filtered_df[filtered_df['overall_rating'].isin(filters['ratings'])]

    # Ownership filter
    if filters['ownership']:
        filtered_df = filtered_df[filtered_df['ownership'].isin(filters['ownership'])]

    # Bed count filter
    if filters['bed_size']:
        bed_masks = []
        if 'Small (1-50)' in filters['bed_size']:
            bed_masks.append((filtered_df['bed_count'] >= 1) & (filtered_df['bed_count'] <= 50))
        if 'Medium (51-100)' in filters['bed_size']:
            bed_masks.append((filtered_df['bed_count'] >= 51) & (filtered_df['bed_count'] <= 100))
        if 'Large (101+)' in filters['bed_size']:
            bed_masks.append(filtered_df['bed_count'] >= 101)

        if bed_masks:
            combined_mask = bed_masks[0]
            for mask in bed_masks[1:]:
                combined_mask = combined_mask | mask
            filtered_df = filtered_df[combined_mask]

    # Search term filter
    if filters['search_term']:
        term = filters['search_term'].lower()
        mask = (
            filtered_df['name'].str.lower().str.contains(term, na=False) |
            filtered_df['city'].str.lower().str.contains(term, na=False) |
            filtered_df['zip'].str.contains(term, na=False)
        )
        filtered_df = filtered_df[mask]

    return filtered_df

# Header
st.markdown('<h1 class="main-header">🏥 Compare SNF: Skilled Nursing Facility Comparison Tool</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Compare Skilled Nursing Facilities Using Official CMS Quality Ratings & Star Ratings | Free SNF Comparison Dashboard</p>', unsafe_allow_html=True)

# Sidebar for search and filters
st.sidebar.header("Search & Filters")

# Search section
with st.sidebar.expander("🔍 Search", expanded=True):
    search_term = st.text_input("Facility, City, or ZIP", placeholder="Enter search term...")

    col1, col2 = st.columns(2)
    with col1:
        state = st.selectbox("State", [""] + [
            "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
            "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
            "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
            "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
            "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
        ])

    with col2:
        if st.button("Search", type="primary"):
            with st.spinner("Searching facilities..."):
                st.session_state.facilities_df = api.search_facilities(
                    state=state if state else None,
                    search_term=search_term if search_term else None,
                    limit=100
                )
                st.success(f"Found {len(st.session_state.facilities_df)} facilities!")

# Filter section
with st.sidebar.expander("🔧 Filters", expanded=True):
    st.subheader("Overall Rating")
    rating_filters = []
    for rating in [5, 4, 3, 2, 1]:
        if st.checkbox(f"{render_stars(rating)}", key=f"rating_{rating}"):
            rating_filters.append(rating)

    st.subheader("Ownership Type")
    ownership_filters = []
    for ownership in ["For profit", "Non profit", "Government"]:
        if st.checkbox(ownership, key=f"ownership_{ownership}"):
            ownership_filters.append(ownership)

    st.subheader("Bed Count")
    bed_filters = st.multiselect(
        "Facility Size",
        ["Small (1-50)", "Medium (51-100)", "Large (101+)"]
    )

    if st.button("Clear All Filters"):
        st.rerun()

# Apply filters
filters = {
    'ratings': rating_filters,
    'ownership': ownership_filters,
    'bed_size': bed_filters,
    'search_term': search_term
}

filtered_df = filter_dataframe(st.session_state.facilities_df, filters)

# Sorting
st.sidebar.subheader("Sort By")
sort_option = st.sidebar.selectbox(
    "Order",
    ["Highest Rated", "Lowest Rated", "Name (A-Z)", "Name (Z-A)", "Most Beds", "Fewest Beds"]
)

# Apply sorting
if sort_option == "Highest Rated":
    filtered_df = filtered_df.sort_values('overall_rating', ascending=False)
elif sort_option == "Lowest Rated":
    filtered_df = filtered_df.sort_values('overall_rating', ascending=True)
elif sort_option == "Name (A-Z)":
    filtered_df = filtered_df.sort_values('name', ascending=True)
elif sort_option == "Name (Z-A)":
    filtered_df = filtered_df.sort_values('name', ascending=False)
elif sort_option == "Most Beds":
    filtered_df = filtered_df.sort_values('bed_count', ascending=False)
elif sort_option == "Fewest Beds":
    filtered_df = filtered_df.sort_values('bed_count', ascending=True)

# Main content area
st.markdown(f"### Showing {len(filtered_df)} of {len(st.session_state.facilities_df)} facilities")

# Tabs for different views
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📋 Facility Cards", "🗺️ Map View", "📊 Analytics", "🔍 Detailed View", "⚖️ Compare", "ℹ️ About"])

# Tab 1: Facility Cards
with tab1:
    if filtered_df.empty:
        st.info("No facilities found. Try adjusting your search or filters.")
    else:
        # Display facilities in a grid
        cols_per_row = 2
        for idx in range(0, len(filtered_df), cols_per_row):
            cols = st.columns(cols_per_row)
            for col_idx, col in enumerate(cols):
                facility_idx = idx + col_idx
                if facility_idx < len(filtered_df):
                    facility = filtered_df.iloc[facility_idx]

                    with col:
                        with st.container():
                            st.markdown(f"### {facility['name']}")
                            st.caption(f"📍 {facility['city']}, {facility['state']} {facility['zip']}")

                            # Overall rating with color
                            rating_color = get_rating_color(facility['overall_rating'])
                            st.markdown(
                                f"<div style='background-color: {rating_color}20; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid {rating_color};'>"
                                f"<h4 style='margin:0; color: {rating_color};'>Overall: {render_stars(facility['overall_rating'])}</h4>"
                                f"</div>",
                                unsafe_allow_html=True
                            )

                            # Sub-ratings
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.metric("Health Inspection", render_stars(facility['health_rating']))
                                st.metric("Quality Measures", render_stars(facility['quality_rating']))
                            with col_b:
                                st.metric("Staffing", render_stars(facility['staffing_rating']))
                                st.metric("Bed Count", facility['bed_count'])

                            # Action buttons
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("View Details", key=f"detail_{facility_idx}_{facility['id']}"):
                                    st.session_state.selected_facility = facility
                                    st.rerun()
                            with col2:
                                if facility['id'] in st.session_state.selected_for_comparison:
                                    if st.button("✓ Remove", key=f"compare_remove_{facility_idx}_{facility['id']}", type="secondary"):
                                        st.session_state.selected_for_comparison.remove(facility['id'])
                                        st.rerun()
                                else:
                                    if st.button("Compare", key=f"compare_add_{facility_idx}_{facility['id']}"):
                                        if len(st.session_state.selected_for_comparison) < 4:
                                            st.session_state.selected_for_comparison.append(facility['id'])
                                            st.rerun()
                                        else:
                                            st.warning("Maximum 4 facilities for comparison")

                            st.markdown("---")

# Tab 2: Map View
with tab2:
    if not filtered_df.empty:
        st.subheader("🗺️ Facility Map")

        # Filter out facilities without coordinates
        map_df = filtered_df.dropna(subset=['latitude', 'longitude'])

        if map_df.empty:
            st.warning("No facilities with valid coordinates to display on map.")
        else:
            # Add hover text
            map_df['hover_text'] = map_df.apply(
                lambda row: f"<b>{row['name']}</b><br>" +
                           f"{row['city']}, {row['state']}<br>" +
                           f"Overall Rating: {render_stars(row['overall_rating'])}<br>" +
                           f"Beds: {row['bed_count']}<br>" +
                           f"Ownership: {row['ownership']}",
                axis=1
            )

            # Create color scale based on rating
            map_df['rating_color'] = map_df['overall_rating'].map({
                5: '#28A745',  # Green
                4: '#90C351',  # Light green
                3: '#FFC107',  # Yellow
                2: '#FF8C42',  # Orange
                1: '#DC3545',  # Red
                0: '#6C757D'   # Gray
            })

            # Create the map
            fig_map = px.scatter_mapbox(
                map_df,
                lat='latitude',
                lon='longitude',
                hover_name='name',
                hover_data={
                    'city': True,
                    'state': True,
                    'overall_rating': True,
                    'bed_count': True,
                    'ownership': True,
                    'latitude': False,
                    'longitude': False,
                    'rating_color': False
                },
                color='overall_rating',
                color_continuous_scale=[
                    [0.0, '#DC3545'],  # 1 star - Red
                    [0.25, '#FF8C42'], # 2 stars - Orange
                    [0.5, '#FFC107'],  # 3 stars - Yellow
                    [0.75, '#90C351'], # 4 stars - Light green
                    [1.0, '#28A745']   # 5 stars - Green
                ],
                size_max=15,
                zoom=3,
                height=600,
                labels={'overall_rating': 'Overall Rating'}
            )

            fig_map.update_layout(
                mapbox_style="open-street-map",
                margin={"r": 0, "t": 0, "l": 0, "b": 0}
            )

            st.plotly_chart(fig_map, use_container_width=True)

            # Map statistics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Facilities on Map", len(map_df))
            with col2:
                avg_rating = map_df['overall_rating'].mean()
                st.metric("Average Rating", f"{avg_rating:.1f}⭐")
            with col3:
                top_rated = len(map_df[map_df['overall_rating'] >= 4])
                st.metric("4+ Star Facilities", top_rated)
            with col4:
                st.metric("States Represented", map_df['state'].nunique())
    else:
        st.info("No facilities to display on map. Try adjusting your search or filters.")

# Tab 3: Analytics
with tab3:
    if not filtered_df.empty:
        st.subheader("Quality Ratings Distribution")

        # Rating distribution
        col1, col2 = st.columns(2)

        with col1:
            # Overall rating distribution
            rating_counts = filtered_df['overall_rating'].value_counts().sort_index()
            fig_ratings = px.bar(
                x=rating_counts.index,
                y=rating_counts.values,
                labels={'x': 'Rating', 'y': 'Number of Facilities'},
                title='Overall Rating Distribution',
                color=rating_counts.index,
                color_continuous_scale=['#DC3545', '#FF8C42', '#FFC107', '#90C351', '#28A745']
            )
            st.plotly_chart(fig_ratings, use_container_width=True)

        with col2:
            # Ownership type distribution
            ownership_counts = filtered_df['ownership'].value_counts()
            fig_ownership = px.pie(
                values=ownership_counts.values,
                names=ownership_counts.index,
                title='Ownership Type Distribution'
            )
            st.plotly_chart(fig_ownership, use_container_width=True)

        # Quality measures comparison
        st.subheader("Quality Measures Averages")
        avg_falls = filtered_df['falls_with_injury'].mean()
        avg_ulcers = filtered_df['pressure_ulcers'].mean()
        avg_uti = filtered_df['uti_rate'].mean()
        avg_antipsychotic = filtered_df['antipsychotic_use'].mean()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Avg Falls with Injury", f"{avg_falls:.1f}%" if pd.notna(avg_falls) else "N/A")
        col2.metric("Avg Pressure Ulcers", f"{avg_ulcers:.1f}%" if pd.notna(avg_ulcers) else "N/A")
        col3.metric("Avg UTI Rate", f"{avg_uti:.1f}%" if pd.notna(avg_uti) else "N/A")
        col4.metric("Avg Antipsychotic Use", f"{avg_antipsychotic:.1f}%" if pd.notna(avg_antipsychotic) else "N/A")

        # Staffing comparison
        st.subheader("Staffing Metrics")
        col1, col2 = st.columns(2)
        with col1:
            avg_rn_hours = filtered_df['rn_hours_per_day'].mean()
            st.metric("Avg RN Hours/Day/Resident", f"{avg_rn_hours:.2f}" if pd.notna(avg_rn_hours) else "N/A")
        with col2:
            avg_total_hours = filtered_df['total_hours_per_day'].mean()
            st.metric("Avg Total Nursing Hours/Day/Resident", f"{avg_total_hours:.2f}" if pd.notna(avg_total_hours) else "N/A")

# Tab 4: Detailed View
with tab4:
    if 'selected_facility' in st.session_state:
        facility = st.session_state.selected_facility

        st.title(f"🏥 {facility['name']}")

        # Contact Information
        st.subheader("📞 Contact Information")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Address:** {facility['address']}")
            st.write(f"**City:** {facility['city']}, {facility['state']} {facility['zip']}")
        with col2:
            st.write(f"**Phone:** {facility['phone']}")
            st.write(f"**Ownership:** {facility['ownership']}")
            st.write(f"**Beds:** {facility['bed_count']}")

        # Quality Ratings
        st.subheader("⭐ Quality Ratings")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Overall", render_stars(facility['overall_rating']))
        with col2:
            st.metric("Health Inspection", render_stars(facility['health_rating']))
        with col3:
            st.metric("Staffing", render_stars(facility['staffing_rating']))
        with col4:
            st.metric("Quality Measures", render_stars(facility['quality_rating']))

        # Staffing Metrics
        st.subheader("👥 Staffing Metrics")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("RN Hours per Resident per Day", f"{facility['rn_hours_per_day']:.2f}" if pd.notna(facility['rn_hours_per_day']) else "N/A")
        with col2:
            st.metric("Total Nursing Hours per Resident per Day", f"{facility['total_hours_per_day']:.2f}" if pd.notna(facility['total_hours_per_day']) else "N/A")

        # Quality Measures
        st.subheader("📊 Quality Measures")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Falls with Major Injury", f"{facility['falls_with_injury']:.1f}%" if pd.notna(facility['falls_with_injury']) else "N/A")
            st.metric("Pressure Ulcers", f"{facility['pressure_ulcers']:.1f}%" if pd.notna(facility['pressure_ulcers']) else "N/A")
        with col2:
            st.metric("UTI Rate", f"{facility['uti_rate']:.1f}%" if pd.notna(facility['uti_rate']) else "N/A")
            st.metric("Antipsychotic Medication Use", f"{facility['antipsychotic_use']:.1f}%" if pd.notna(facility['antipsychotic_use']) else "N/A")

        # Inspection Deficiencies
        st.subheader("🔍 Inspection Deficiencies")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Health Deficiencies", facility['health_deficiencies'])
        with col2:
            st.metric("Fire Safety Deficiencies", facility['fire_deficiencies'])

    else:
        st.info("Select a facility from the 'Facility Cards' tab to view detailed information.")

# Tab 5: Comparison
with tab5:
    # Debug info
    st.write(f"**Debug:** Selected facility IDs: {st.session_state.selected_for_comparison}")
    st.write(f"**Debug:** Number selected: {len(st.session_state.selected_for_comparison)}")

    if len(st.session_state.selected_for_comparison) >= 2:
        # Use the full dataset, not filtered_df, to find selected facilities
        comparison_df = st.session_state.facilities_df[st.session_state.facilities_df['id'].isin(st.session_state.selected_for_comparison)]

        st.subheader(f"Comparing {len(comparison_df)} Facilities")

        # Create comparison table
        comparison_data = {
            "Facility": comparison_df['name'].tolist(),
            "City": comparison_df['city'].tolist(),
            "Overall Rating": [render_stars(r) for r in comparison_df['overall_rating'].tolist()],
            "Health Rating": [render_stars(r) for r in comparison_df['health_rating'].tolist()],
            "Staffing Rating": [render_stars(r) for r in comparison_df['staffing_rating'].tolist()],
            "Quality Rating": [render_stars(r) for r in comparison_df['quality_rating'].tolist()],
            "Ownership": comparison_df['ownership'].tolist(),
            "Bed Count": comparison_df['bed_count'].tolist(),
            "RN Hours/Day": [f"{v:.2f}" if pd.notna(v) else "N/A" for v in comparison_df['rn_hours_per_day'].tolist()],
            "Total Hours/Day": [f"{v:.2f}" if pd.notna(v) else "N/A" for v in comparison_df['total_hours_per_day'].tolist()],
            "Falls w/ Injury (%)": [f"{v:.1f}" if pd.notna(v) else "N/A" for v in comparison_df['falls_with_injury'].tolist()],
            "Pressure Ulcers (%)": [f"{v:.1f}" if pd.notna(v) else "N/A" for v in comparison_df['pressure_ulcers'].tolist()],
            "UTI Rate (%)": [f"{v:.1f}" if pd.notna(v) else "N/A" for v in comparison_df['uti_rate'].tolist()],
            "Health Deficiencies": comparison_df['health_deficiencies'].tolist(),
        }

        st.dataframe(pd.DataFrame(comparison_data), use_container_width=True)

        # Visual comparison of ratings
        st.subheader("Rating Comparison")
        fig = go.Figure()

        for _, facility in comparison_df.iterrows():
            fig.add_trace(go.Scatterpolar(
                r=[
                    facility['overall_rating'],
                    facility['health_rating'],
                    facility['staffing_rating'],
                    facility['quality_rating'],
                    facility['rn_rating']
                ],
                theta=['Overall', 'Health', 'Staffing', 'Quality', 'RN Staffing'],
                fill='toself',
                name=facility['name']
            ))

        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
            showlegend=True
        )

        st.plotly_chart(fig, use_container_width=True)

        if st.button("Clear Comparison"):
            st.session_state.selected_for_comparison = []
            st.rerun()

    else:
        st.info("Select at least 2 facilities from the 'Facility Cards' tab to compare them.")
        st.write(f"Currently selected: {len(st.session_state.selected_for_comparison)} facilities")

# Tab 6: About
with tab6:
    st.title("About This SNF Comparison Tool")

    st.markdown("""
    ## Compare Skilled Nursing Facilities (SNF) with Confidence

    ### What is This Tool?

    The **SNF Comparison Dashboard** is a free, comprehensive tool that helps you **compare skilled nursing facilities** using official CMS (Centers for Medicare & Medicaid Services) data. Whether you're searching for quality nursing homes for yourself, a loved one, or conducting healthcare research, our platform provides transparent, data-driven insights to make informed decisions.

    ### Why Compare SNF Quality Ratings?

    Choosing the right **skilled nursing facility** is one of the most important healthcare decisions you can make. Not all nursing homes provide the same level of care, and quality can vary significantly even within the same geographic area. Our SNF comparison tool helps you:

    - **Identify top-rated nursing facilities** in your area based on CMS 5-star quality ratings
    - **Compare nursing home quality measures** including health inspections, staffing levels, and patient outcomes
    - **Make informed decisions** backed by official government data
    - **Understand facility strengths and weaknesses** through detailed quality metrics
    - **Visualize facility locations** on an interactive map

    ### Key Features for Comparing SNF Facilities

    #### 🔍 Advanced Search & Filtering
    - Search by **state, city, ZIP code, or facility name**
    - Filter by **star ratings** (1-5 stars based on CMS quality ratings)
    - Filter by **ownership type** (for-profit, non-profit, government)
    - Filter by **facility size** (bed count)
    - Sort results by rating, name, or bed count

    #### 🗺️ Interactive Map View
    - Visualize nursing facilities on an interactive map
    - Color-coded markers show quality ratings at a glance
    - Click markers to view detailed facility information
    - Compare multiple facilities in the same geographic area

    #### 📊 Quality Metrics & Analytics
    Our SNF comparison tool displays comprehensive quality measures including:

    **Rating Categories:**
    - Overall quality rating (1-5 stars)
    - Health inspection rating
    - Staffing rating
    - Quality measures rating
    - RN (Registered Nurse) staffing rating

    **Patient Outcomes:**
    - Falls with major injury rates
    - Pressure ulcer (bedsore) rates
    - Urinary tract infection (UTI) rates
    - Antipsychotic medication usage rates

    **Staffing Metrics:**
    - RN hours per resident per day
    - Total nursing hours per resident per day

    **Compliance Data:**
    - Health inspection deficiencies
    - Fire safety deficiencies

    #### ⚖️ Side-by-Side Comparison
    - Compare up to 4 facilities simultaneously
    - View all quality metrics in one comprehensive table
    - Radar chart visualization for easy comparison
    - Identify the best nursing home for your specific needs

    ### How to Use This SNF Comparison Tool

    **Step 1: Search for Facilities**
    - Use the sidebar to enter your **state** or search term
    - Apply filters to narrow down results based on ratings, ownership, or size

    **Step 2: Review Facility Cards**
    - Browse facilities in the **Facility Cards** tab
    - View star ratings, bed counts, and key metrics at a glance
    - Click "View Details" for comprehensive facility information

    **Step 3: Explore the Map**
    - Switch to the **Map View** tab to see facility locations
    - Identify nursing homes near you or your loved one
    - Use color-coded markers to spot top-rated facilities quickly

    **Step 4: Analyze Quality Data**
    - Visit the **Analytics** tab for distribution insights
    - Understand industry benchmarks and averages
    - Compare facility performance against regional norms

    **Step 5: Compare Facilities**
    - Select 2-4 facilities using the "Compare" button
    - View side-by-side comparison in the **Compare** tab
    - Make your final decision based on comprehensive data

    ### Understanding CMS Star Ratings for Nursing Homes

    The **CMS 5-star quality rating system** is the gold standard for evaluating skilled nursing facilities:

    - ⭐⭐⭐⭐⭐ **5 Stars (Excellent)**: Well above average quality
    - ⭐⭐⭐⭐ **4 Stars (Above Average)**: Better than average quality
    - ⭐⭐⭐ **3 Stars (Average)**: Average quality
    - ⭐⭐ **2 Stars (Below Average)**: Below average quality
    - ⭐ **1 Star (Much Below Average)**: Much below average quality

    The overall rating combines:
    1. **Health Inspections** (50% weight) - Based on onsite surveys
    2. **Staffing** (25% weight) - RN and total nurse staffing hours
    3. **Quality Measures** (25% weight) - Patient health and safety outcomes

    ### Who Should Use This SNF Comparison Tool?

    Our platform is designed for:

    - **Families** searching for quality care for elderly parents or relatives
    - **Healthcare professionals** making referral recommendations
    - **Hospital discharge planners** identifying appropriate post-acute care facilities
    - **Researchers** analyzing nursing home quality trends
    - **Advocates** working to improve long-term care quality
    - **Anyone** seeking to compare skilled nursing facilities objectively

    ### Data Source & Accuracy

    All data is sourced directly from the **CMS Provider Data Catalog**, which includes:
    - Official nursing home quality ratings
    - Quarterly updated inspection results
    - Verified staffing information
    - Patient health outcome measures

    Data is refreshed regularly to ensure you have access to the most current information when comparing SNF facilities.

    ### Frequently Asked Questions About SNF Comparison

    **Q: What's the difference between a nursing home and a skilled nursing facility?**
    A: "Skilled nursing facility" (SNF) and "nursing home" are often used interchangeably. SNFs provide 24-hour nursing care and medical services for patients who require ongoing medical attention.

    **Q: How often are CMS ratings updated?**
    A: CMS updates nursing home ratings monthly based on the most recent inspection and quality data.

    **Q: Should I only consider 5-star facilities?**
    A: Not necessarily. While higher ratings indicate better performance, consider location, specialized services, and personal preferences. A 4-star facility closer to family may be better than a 5-star facility far away.

    **Q: Are all nursing homes in the database?**
    A: Our tool includes all Medicare and Medicaid certified skilled nursing facilities in the United States - over 15,000 facilities nationwide.

    **Q: Is this tool free to use?**
    A: Yes! This SNF comparison tool is completely free and requires no registration.

    ### Next Steps in Your SNF Search

    After comparing skilled nursing facilities online:

    1. **Schedule tours** at your top 2-3 choices
    2. **Ask questions** about care plans, staffing ratios, and family involvement
    3. **Meet the staff** who will be providing care
    4. **Review contracts carefully** before making commitments
    5. **Trust your instincts** - data is important, but so is your personal impression

    ### Privacy & Disclaimer

    This tool displays publicly available CMS data. We do not collect personal information. This tool is for informational purposes only and should not replace professional medical advice or personal facility visits when selecting a nursing home.

    ---

    ### Keywords for Healthcare Seekers

    *Compare skilled nursing facilities, SNF comparison tool, nursing home ratings, CMS 5-star ratings, skilled nursing facility quality, compare nursing homes, SNF quality ratings, nursing facility comparison, Medicare nursing homes, find skilled nursing facilities, nursing home quality data, SNF star ratings, compare SNF care, skilled nursing facility search, nursing home quality comparison*
    """)

    st.markdown("---")
    st.info("💡 **Ready to compare SNF facilities?** Click on the **Facility Cards** or **Map View** tab to start exploring quality nursing homes in your area!")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #6C757D;'>
    <p>Data sourced from <a href='https://data.cms.gov/provider-data'>CMS Provider Data</a></p>
    <p><small>This tool is for informational purposes only. Please verify all information with official sources.</small></p>
</div>
""", unsafe_allow_html=True)
