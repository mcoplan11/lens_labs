# SNF Comparison Dashboard

An interactive Python dashboard for comparing Skilled Nursing Facilities (SNFs) using publicly available CMS (Centers for Medicare & Medicaid Services) data.

## Overview

This dashboard enables users to search, filter, compare, and analyze nursing home quality metrics from the CMS Care Compare database. Built with Python and Streamlit, it provides an intuitive, interactive interface for exploring nursing facility data.

## Features

### ✅ Implemented (v2.0 - Python Version)

1. **Search & Filter**
   - Search by facility name, city, or ZIP code
   - Filter by state (all 50 states)
   - Filter by star rating (1-5 stars)
   - Filter by ownership type (For-profit, Non-profit, Government)
   - Filter by bed count (Small, Medium, Large)
   - Real-time filtering and search

2. **Facility Display**
   - Card-based layout showing key metrics
   - Overall star rating with color coding
   - Sub-ratings for health inspection, staffing, and quality measures
   - Multiple sorting options (rating, name, bed count)
   - Clear, accessible display

3. **Analytics Dashboard**
   - Rating distribution charts
   - Ownership type distribution (pie chart)
   - Quality measures averages
   - Staffing metrics averages
   - Interactive visualizations with Plotly

4. **Facility Details**
   - Dedicated detail view with comprehensive information
   - Contact information and address
   - Detailed quality ratings
   - Staffing metrics (RN hours, total nursing hours)
   - Quality measures (falls, pressure ulcers, UTI rates, etc.)
   - Inspection deficiency counts

5. **Comparison Feature**
   - Compare up to 4 facilities side-by-side
   - Comprehensive comparison table
   - Radar chart visualization for rating comparison
   - All quality metrics and ratings displayed
   - Easy selection/deselection

6. **Data Management**
   - CMS API integration
   - In-memory caching (1-hour cache)
   - Sample data for demo mode
   - Error handling and fallback mechanisms
   - Pandas DataFrame for efficient data processing

## Project Structure

```
nursing_home_dashboard/
├── app.py                  # Main Streamlit dashboard application
├── cms_api.py             # CMS API integration and data processing module
├── requirements.txt       # Python dependencies
├── Interactive SNF.md     # Project requirements document
├── README.md             # This file
└── data/
    └── cache/            # (For future file-based caching)
```

## Technology Stack

- **Python 3.8+**: Core programming language
- **Streamlit**: Interactive web dashboard framework
- **Pandas**: Data manipulation and analysis
- **Requests**: HTTP requests to CMS API
- **Plotly**: Interactive visualizations and charts
- **NumPy**: Numerical computations

## Getting Started

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Virtual environment (recommended)

### Installation

1. **Clone or navigate to the repository:**
   ```bash
   cd nursing_home_dashboard
   ```

2. **Create and activate virtual environment (recommended):**
   ```bash
   # Create virtual environment
   python3 -m venv venv

   # Activate on macOS/Linux
   source venv/bin/activate

   # Activate on Windows
   venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Running the Dashboard

1. **Start the Streamlit app:**
   ```bash
   streamlit run app.py
   ```

2. **Access the dashboard:**
   - The browser should open automatically
   - Or navigate to `http://localhost:8501`

3. **The dashboard loads with sample data by default**
   - Use the state dropdown and search button to fetch real CMS data
   - Apply filters in the sidebar
   - Explore the different tabs

## Usage Guide

### Searching for Facilities

1. **By State**: Select a state from the dropdown in the sidebar
2. **By Search Term**: Enter facility name, city, or ZIP code
3. **Click "Search"**: Fetches facilities from CMS API
4. **Sample Data**: Dashboard starts with 4 sample California facilities

### Filtering Results

Use the sidebar filters:
- **Overall Rating**: Check boxes for 1-5 star ratings
- **Ownership Type**: Select For profit, Non profit, or Government
- **Bed Count**: Choose facility size (Small, Medium, Large)
- **Clear All Filters**: Reset all filters to default

### Sorting Results

Use the "Sort By" dropdown in sidebar:
- Highest Rated / Lowest Rated
- Name (A-Z) / Name (Z-A)
- Most Beds / Fewest Beds

### Viewing Facility Details

1. Navigate to **"📋 Facility Cards"** tab
2. Click **"View Details"** on any facility card
3. Switch to **"🔍 Detailed View"** tab to see comprehensive information

### Comparing Facilities

1. In **"📋 Facility Cards"** tab, click **"Compare"** on desired facilities
2. Select up to 4 facilities
3. Navigate to **"⚖️ Compare"** tab
4. View side-by-side comparison table and radar chart
5. Click **"Clear Comparison"** to start over

### Analytics

1. Navigate to **"📊 Analytics"** tab
2. View rating distribution charts
3. See ownership type breakdown
4. Check quality measure averages
5. Review staffing metrics

## Dashboard Tabs

### 1. 📋 Facility Cards
- Browse all facilities in card format
- View key metrics at a glance
- Select facilities for comparison
- Access detailed views

### 2. 📊 Analytics
- Overall rating distribution (bar chart)
- Ownership type distribution (pie chart)
- Quality measures averages
- Staffing metrics summary

### 3. 🔍 Detailed View
- Comprehensive facility information
- Contact details
- All quality ratings
- Staffing metrics
- Quality measures
- Inspection deficiencies

### 4. ⚖️ Compare
- Side-by-side facility comparison
- Comprehensive comparison table
- Radar chart visualization
- Easy comparison of all metrics

## Color Coding System

Ratings are color-coded for quick visual assessment:
- 🟢 **5 Stars**: Green (#28A745) - Excellent
- 🟢 **4 Stars**: Light Green (#90C351) - Above Average
- 🟡 **3 Stars**: Amber (#FFC107) - Average
- 🟠 **2 Stars**: Orange (#FF8C42) - Below Average
- 🔴 **1 Star**: Red (#DC3545) - Poor
- ⚪ **Not Rated**: Gray (#6C757D)

## Data Sources

All facility data comes from:
- [CMS Provider Data API](https://data.cms.gov/provider-data/api)
- Dataset: Nursing Homes Including Rehab Services (ID: 4pq5-n9py)
- [Five-Star Quality Rating System](https://www.cms.gov/medicare/provider-enrollment-and-certification/certificationandcomplianc/fsqrs)

## Key Metrics Explained

### Overall Rating (1-5 Stars)
Composite score based on health inspections, staffing, and quality measures.

### Health Inspection Rating
Based on deficiencies found during state health inspections.

### Staffing Rating
Based on hours of care provided by nursing staff per resident per day.

### Quality Measure Rating
Based on resident outcomes like falls, pressure ulcers, and medication use.

### RN Staffing Hours
Registered Nurse hours per resident per day (higher is better).

### Quality Measures
- **Falls with Major Injury**: Percentage of residents experiencing falls with injury
- **Pressure Ulcers**: Percentage of high-risk residents with pressure sores
- **UTI Rate**: Percentage of residents with urinary tract infections
- **Antipsychotic Use**: Percentage receiving antipsychotic medications

## Module Documentation

### app.py
Main Streamlit application with UI components.
- Multi-tab interface (Cards, Analytics, Details, Compare)
- Interactive filters and search
- Data visualization with Plotly
- Session state management for selections

### cms_api.py
CMS API integration and data processing.

**Class: `CMSAPI`**
- `search_facilities(state, search_term, limit)`: Fetch and filter facilities
- `_process_data(raw_data)`: Transform API response to DataFrame
- `_parse_rating(value)`: Parse and validate rating values
- `_parse_float(value)`: Parse and validate float values
- `_filter_by_search(df, search_term)`: Filter DataFrame by search term
- `_get_sample_data()`: Return sample facilities for demo
- `clear_cache()`: Clear all cached data

## Performance Optimizations

- In-memory caching (1-hour duration)
- Pandas DataFrames for efficient data manipulation
- Streamlit caching for API instance
- Lazy loading of detailed data
- Efficient filtering and sorting operations

## Future Enhancements

### Phase 2
- [ ] Geographic radius search
- [ ] Interactive map view with Folium
- [ ] Export comparison to PDF/CSV
- [ ] Historical trend charts
- [ ] Advanced filtering options

### Phase 3
- [ ] User saved favorites
- [ ] Custom metric calculations
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Download facility reports

## Development Notes

### API Integration

The dashboard uses the CMS Provider Data API. The app includes sample data for demo purposes and falls back to sample data if API calls fail.

For production deployment:
1. Consider implementing request rate limiting
2. Add file-based persistent caching
3. Monitor API usage and quotas
4. Implement error logging

### Caching Strategy

- Cache duration: 1 hour (configurable in `cms_api.py`)
- Cache key format: `{state}_{search_term}_{limit}`
- Automatic cache invalidation after duration
- Manual cache clear via `clear_cache()` method

### Customization

#### Color Scheme
Edit CSS in `app.py` within the `st.markdown()` section:
```python
st.markdown("""
<style>
    .main-header { color: #0066CC; }
    .rating-5 { color: #28A745; }
    /* ... */
</style>
""", unsafe_allow_html=True)
```

#### Cache Duration
Edit in `cms_api.py`:
```python
def __init__(self):
    self.cache = {}
    self.cache_duration = timedelta(hours=1)  # Change duration here
```

#### Sample Data
Edit the `_get_sample_data()` method in `cms_api.py` to modify or add sample facilities.

## Troubleshooting

### Common Issues

**Dashboard won't start:**
```bash
# Make sure dependencies are installed
pip install -r requirements.txt

# Check Python version (3.8+ required)
python --version
```

**API errors:**
- Check internet connection
- CMS API may be temporarily unavailable (sample data will be used automatically)
- Verify API endpoint in `cms_api.py`

**No data displayed:**
- Try searching for a specific state
- Use the sample data (loaded by default)
- Check console for error messages

## Contributing

This is a demonstration project. For improvements:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project uses publicly available CMS data. Please review CMS terms of service for data usage restrictions.

## Disclaimer

This tool is for informational purposes only. Users should verify all information with official CMS sources before making healthcare decisions. The quality ratings and metrics are based on CMS data and may not reflect current facility conditions.

## Support & Resources

- [Streamlit Documentation](https://docs.streamlit.io/)
- [CMS Provider Data Documentation](https://data.cms.gov/provider-data/api)
- [Nursing Home Compare Data Dictionary](https://data.cms.gov/provider-data/sites/default/files/data_dictionaries/nursing_home/NH_Data_Dictionary.pdf)
- [Five-Star Rating System Guide](https://www.cms.gov/medicare/provider-enrollment-and-certification/certificationandcomplianc/fsqrs)

## Changelog

### v2.0 (Current - Python Version)
- Complete rewrite in Python with Streamlit
- Interactive multi-tab interface
- Real-time filtering and search
- Analytics dashboard with charts
- Radar chart for facility comparison
- Pandas-based data processing
- Plotly visualizations
- In-memory caching

### v1.0 (JavaScript Version - Deprecated)
- Vanilla JavaScript implementation
- HTML/CSS/JS stack
- Basic search and filter
- Facility comparison
- Modal-based UI

---

**Built with ❤️ for better healthcare transparency using Python & Streamlit**
