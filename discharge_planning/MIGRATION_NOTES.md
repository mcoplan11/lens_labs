# Migration Notes - CMS Star Rating Tracker v2.0

## What Changed?

The CMS Star Rating Tracker has been completely rewritten and the data source has been migrated from the deprecated Socrata API to the current CMS CSV data format.

## Breaking Changes

### Old API (Deprecated)
```
❌ https://data.cms.gov/resource/4pq5-n9py.json
Status: 410 Gone (API no longer available)
```

### New Data Source
```
✅ CSV files from CMS metadata API
Dynamically fetched from: https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/4pq5-n9py
```

## Key Differences

### 1. Data Format
- **Old**: JSON API with query parameters (Socrata SODA API)
- **New**: CSV file downloads with complete dataset

### 2. Historical Data
- **Old**: Could query historical month_year data directly
- **New**: Single snapshot per CSV file (monthly updates)
  - **Important**: The script now relies on the history file (`cms_rating_history.csv`) to track changes over time
  - First run will not detect changes (need at least 2 data points)
  - Run monthly to build up historical data

### 3. Column Names
The CSV uses different column naming conventions:

| Old API | New CSV (2025) |
|---------|---------|
| `federal_provider_number` | `CMS Certification Number (CCN)` |
| `provider_name` | `Provider Name` |
| `city` | `City/Town` |
| `state` | `State` |
| `overall_rating` | `Overall Rating` |
| `quality_measures_rating` | `QM Rating` |
| `staffing_rating` | `Staffing Rating` |
| `health_inspection_rating` | `Health Inspection Rating` |
| `month_year` | `Processing Date` |

### 4. Performance
- **Old**: Fast, filtered queries (~1 second)
- **New**: Downloads complete CSV (~30-60 seconds, ~15-20MB file)
  - Filters locally after download
  - Acceptable tradeoff for reliability

## How to Use the New Version

### First-Time Setup
```bash
# 1. Activate your virtual environment
source .venv/bin/activate

# 2. Install/update dependencies
pip install -r requirements.txt

# 3. First run - establishes baseline
python track_cms_star_rating_change.py --ccn 455682 675791 676336

# Output: No changes detected (expected - first run)
```

### Building Historical Data
To detect changes, you need to run the script at least twice:

```bash
# Run 1 (today)
python track_cms_star_rating_change.py --ccn 455682 675791 676336
# Creates: cms_rating_history.csv with current snapshot

# Run 2 (next month or after CMS updates data)
python track_cms_star_rating_change.py --ccn 455682 675791 676336
# Compares new data with history, detects changes
```

### Recommended Schedule
- **Monthly**: Run after CMS updates (typically 1st of each month)
- **Automated**: Set up cron job or Task Scheduler (see README)

## New Features in v2.0

1. **Object-Oriented Design**
   - Clean `CMSStarRatingTracker` class
   - Modular, testable methods
   - Type hints throughout

2. **Enhanced Logging**
   - Console and file logging (`cms_tracker.log`)
   - Verbose (`-v`) and quiet (`-q`) modes
   - Detailed error messages

3. **Flexible Configuration**
   - CLI arguments for all options
   - JSON config file support
   - CCN watchlist files

4. **Better Output**
   - Visual direction indicators (↑/↓)
   - Formatted console output
   - CSV export with timestamps
   - Trend analysis reports

5. **Notifications**
   - Email alerts (SMTP)
   - Webhook support (Slack, Discord, etc.)
   - Configurable via JSON

6. **Robust Error Handling**
   - Automatic retries with backoff
   - Graceful failure modes
   - Comprehensive exception handling

## Migration Checklist

- [x] Update API endpoint from Socrata to CSV
- [x] Add metadata API integration
- [x] Map new CSV column names
- [x] Update documentation
- [x] Add troubleshooting guide
- [x] Create example files (config, watchlist)
- [x] Add comprehensive README

## Known Limitations

1. **CSV Download Size**: The complete dataset is ~15-20MB
   - Takes 30-60 seconds to download
   - Acceptable for monthly/daily runs
   - Consider caching if running very frequently

2. **Single Snapshot**: Each CSV is a point-in-time snapshot
   - No built-in historical data in the CSV
   - Must maintain local history file
   - Don't delete `cms_rating_history.csv`!

3. **Date Field**: The CSV has a single "Processing Date"
   - Not the same as the old `month_year` field
   - Represents when CMS published the data
   - All records in a CSV share the same date

## Testing the Update

### Quick Test (without dependencies)
```bash
# Test metadata API is accessible
curl -s "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/4pq5-n9py" | grep -o "downloadURL.*csv" | head -1
```

### Full Test (with dependencies)
```bash
source .venv/bin/activate
python track_cms_star_rating_change.py --ccn 455682 675791 676336 -v
```

Expected output:
```
2025-10-22 XX:XX:XX - INFO - Tracking 3 providers: 455682, 675791, 676336
2025-10-22 XX:XX:XX - INFO - Fetching latest dataset metadata from CMS...
2025-10-22 XX:XX:XX - INFO - Found CSV URL: https://data.cms.gov/.../NH_ProviderInfo_...csv
2025-10-22 XX:XX:XX - INFO - Downloading provider data CSV...
2025-10-22 XX:XX:XX - INFO - Downloaded CSV with XXXXX total records
2025-10-22 XX:XX:XX - INFO - Filtered to 3 records for tracked providers
2025-10-22 XX:XX:XX - INFO - Normalized data: 3 valid records
...
```

## Support

If you encounter issues:

1. **Check the README**: Comprehensive troubleshooting section
2. **Enable verbose logging**: Run with `-v` flag
3. **Review logs**: Check `cms_tracker.log`
4. **Verify dependencies**: `pip list | grep -E "pandas|requests"`
5. **Test metadata API**: Run `python test_metadata.py`

## Version History

### v2.0 (Current) - October 2025
- Migrated from Socrata API to CMS CSV
- Complete rewrite with OOP design
- Added notifications, trends, exports
- Enhanced error handling and logging

### v1.0 - Original
- Used Socrata JSON API
- Simple script with hardcoded CCNs
- Basic console output

---

**Note**: Keep your `cms_rating_history.csv` file safe! It's your historical tracking database.
