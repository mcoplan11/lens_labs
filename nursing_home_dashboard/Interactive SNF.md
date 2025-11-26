# Interactive SNF (Nursing Home) Comparison Dashboard

## Project Overview
Create an interactive HTML-based dashboard for comparing Skilled Nursing Facilities (SNFs) using publicly available CMS data. The dashboard should enable users to easily explore, compare, and analyze nursing home quality metrics.

## Core Features

### 1. Data Integration
- **Primary Data Source**: CMS Care Compare API and downloadable datasets
  - Provider Information API: https://data.cms.gov/provider-data/api
  - Nursing Home Compare datasets
  - Five-Star Quality Rating System data
  - Health Inspection data
  - Staffing data
  - Quality Measures data
  
### 2. Search & Filter Functionality
- **Geographic Search**: 
  - Search by ZIP code, city, or state
  - Radius-based search (e.g., "within 25 miles of ZIP")
- **Advanced Filters**:
  - Overall star rating (1-5 stars)
  - Health inspection rating
  - Staffing rating
  - Quality measure rating
  - Ownership type (for-profit, non-profit, government)
  - Bed count ranges
  - Special care units (Alzheimer's, ventilator, etc.)

### 3. Comparison Features
- **Side-by-Side Comparison**: 
  - Compare up to 4 facilities simultaneously
  - Highlight differences in key metrics
  - Visual indicators for above/below average performance
- **Ranking System**:
  - Sort facilities by various metrics
  - Show percentile rankings within state/national averages

### 4. Quality Metrics Display
- **CMS Five-Star Ratings**:
  - Overall rating
  - Health inspections
  - Staffing
  - Quality measures
  - RN staffing
- **Key Quality Indicators**:
  - Falls with major injury
  - Pressure ulcers
  - UTI rates
  - Antipsychotic medication use
  - Rehospitalization rates
  - Emergency department visits
- **Staffing Metrics**:
  - RN hours per resident per day
  - Total nursing hours per resident per day
  - Staff turnover rates
  - Weekend staffing levels
- **Health Inspections**:
  - Number of citations
  - Severity of deficiencies
  - Complaint inspection results
  - Infection control citations

### 5. Visualizations
- **Charts & Graphs**:
  - Star rating distribution (bar/donut charts)
  - Trend lines for quality measures over time
  - Staffing level comparisons (horizontal bar charts)
  - Geographic heat maps for regional quality
- **Interactive Elements**:
  - Tooltips with detailed explanations
  - Expandable sections for deep dives
  - Color-coded performance indicators

### 6. User Interface Requirements
- **Responsive Design**: Mobile-friendly, works on tablets and desktops
- **Accessibility**: WCAG 2.1 AA compliant
- **Performance**: Fast loading, efficient data handling
- **Modern UI**: Clean, professional healthcare aesthetic

## Technical Implementation

### File Structure
```
snf-dashboard/
├── index.html          # Main dashboard page
├── css/
│   └── styles.css      # Custom styles
├── js/
│   ├── main.js         # Core application logic
│   ├── api.js          # CMS API integration
│   ├── charts.js       # Chart rendering logic
│   ├── comparison.js   # Comparison functionality
│   └── filters.js      # Search and filter logic
├── data/
│   └── cache/          # Cached API responses
└── README.md           # This file
```

### Technology Stack
- **HTML5**: Semantic markup
- **CSS3**: Modern styling with CSS Grid/Flexbox
- **JavaScript (ES6+)**: No framework required, vanilla JS
- **Libraries**:
  - Chart.js or D3.js for visualizations
  - Papa Parse for CSV parsing (if using downloadable datasets)
  - Fuse.js for fuzzy search functionality
  - Leaflet.js for interactive maps (optional)

### Data Fetching Strategy
1. **Initial Load**: Fetch data for user's geographic area
2. **Caching**: Store frequently accessed data in localStorage
3. **Lazy Loading**: Load detailed facility data on demand
4. **Batch Requests**: Minimize API calls through intelligent batching
5. **Fallback Data**: Include sample dataset for demo/offline mode

### Key Components to Build

#### 1. Search Component
```javascript
// Features needed:
- Autocomplete for facility names
- Geographic search with radius
- Real-time filtering as user types
- Search history/recent searches
```

#### 2. Filter Panel
```javascript
// Features needed:
- Collapsible filter categories
- Multi-select options
- Range sliders for numeric filters
- Clear all filters button
- Save filter presets
```

#### 3. Results Grid
```javascript
// Features needed:
- Card-based layout for facilities
- Quick view of key metrics
- Add to comparison button
- Pagination or infinite scroll
- Export results to CSV
```

#### 4. Comparison Table
```javascript
// Features needed:
- Sticky headers
- Sortable columns
- Highlight best/worst values
- Print-friendly view
- Share comparison via URL
```

#### 5. Detail Modal
```javascript
// Features needed:
- Comprehensive facility information
- Historical data trends
- Downloadable facility report
- Contact information
- Directions/map integration
```

## API Integration Examples

### CMS Provider Data API
```javascript
// Example endpoint for nursing home data
const baseURL = 'https://data.cms.gov/provider-data/api/1/datastore/query';
const dataset = '4pq5-n9py'; // Nursing homes including rehab services

// Query parameters
const params = {
  'filter[state]': 'CA',
  'filter[overall_rating]': '5',
  'page[size]': 50
};
```

### Data Processing
```javascript
// Process and normalize CMS data
function processNursingHomeData(rawData) {
  return {
    id: rawData.federal_provider_number,
    name: rawData.provider_name,
    address: formatAddress(rawData),
    ratings: {
      overall: parseInt(rawData.overall_rating),
      health: parseInt(rawData.health_inspection_rating),
      staffing: parseInt(rawData.staffing_rating),
      quality: parseInt(rawData.quality_measure_rating)
    },
    metrics: extractQualityMetrics(rawData),
    // ... additional processing
  };
}
```

## UI/UX Specifications

### Color Scheme
- Primary: Healthcare blue (#0066CC)
- Success: Green (#28A745) for above-average metrics
- Warning: Amber (#FFC107) for average metrics
- Danger: Red (#DC3545) for below-average metrics
- Neutral: Grays for UI elements

### Typography
- Headers: System fonts with fallbacks
- Body: Readable sans-serif (16px minimum)
- Data tables: Monospace for numbers

### Responsive Breakpoints
- Mobile: < 768px (single column layout)
- Tablet: 768px - 1024px (2-column layout)
- Desktop: > 1024px (full dashboard)

## Performance Optimization
- Implement virtual scrolling for large lists
- Use debouncing for search inputs
- Lazy load images and non-critical resources
- Minimize and bundle CSS/JS files
- Enable gzip compression
- Implement service worker for offline functionality

## Accessibility Features
- Keyboard navigation support
- Screen reader friendly labels
- High contrast mode option
- Focus indicators
- Skip navigation links
- ARIA labels for interactive elements

## Testing Considerations
- Cross-browser testing (Chrome, Firefox, Safari, Edge)
- Mobile device testing
- Performance testing with large datasets
- Accessibility testing with screen readers
- Unit tests for data processing functions
- Integration tests for API calls

## Future Enhancements
- User accounts for saving favorites
- Email alerts for quality rating changes
- Advanced analytics and predictive modeling
- Integration with Medicare.gov accounts
- Family review integration
- Virtual tour integration
- Multi-language support

## Development Notes
- Start with core search and display functionality
- Add comparison features in phase 2
- Implement advanced filters and visualizations in phase 3
- Focus on performance optimization throughout
- Ensure all CMS data usage complies with their terms of service

## Resources
- [CMS Provider Data API Documentation](https://data.cms.gov/provider-data/api)
- [Nursing Home Compare Data Dictionary](https://data.cms.gov/provider-data/sites/default/files/data_dictionaries/nursing_home/NH_Data_Dictionary.pdf)
- [Five-Star Quality Rating System](https://www.cms.gov/medicare/provider-enrollment-and-certification/certificationandcomplianc/fsqrs)

## Sample Code Structure for index.html
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SNF Comparison Dashboard</title>
    <!-- Include CSS -->
</head>
<body>
    <!-- Header with search bar -->
    <header id="main-header">
        <div class="search-container">
            <!-- Search implementation -->
        </div>
    </header>
    
    <!-- Filter sidebar -->
    <aside id="filter-panel">
        <!-- Filter controls -->
    </aside>
    
    <!-- Main content area -->
    <main id="dashboard-content">
        <!-- Results grid -->
        <section id="results-grid">
            <!-- Facility cards -->
        </section>
        
        <!-- Comparison panel -->
        <section id="comparison-panel" class="hidden">
            <!-- Comparison table -->
        </section>
    </main>
    
    <!-- Detail modal -->
    <div id="facility-modal" class="modal">
        <!-- Detailed facility view -->
    </div>
    
    <!-- Include JavaScript files -->
</body>
</html>
```

This README provides a comprehensive blueprint for building the SNF comparison dashboard. The code should be modular, well-commented, and follow best practices for maintainability and scalability.