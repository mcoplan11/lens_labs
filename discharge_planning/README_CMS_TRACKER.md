# CMS Star Rating Tracker

A professional Python tool for monitoring CMS (Centers for Medicare & Medicaid Services) star ratings for nursing homes and healthcare providers. Track changes in ratings over time, analyze trends, and receive automated alerts.

## Features

- **Real-time Monitoring**: Fetch latest ratings from CMS public API
- **Change Detection**: Automatically detect rating changes across multiple metrics
- **Historical Tracking**: Save data to CSV for long-term trend analysis
- **Trend Analysis**: Statistical summaries showing min/max/average ratings over time
- **Multiple Output Formats**: Console output, CSV export, and structured data
- **Notification Support**: Email and webhook alerts for rating changes
- **Robust Error Handling**: Automatic retries, comprehensive logging
- **Flexible Configuration**: CLI arguments, config files, and CCN watchlists
- **Type Safety**: Full type hints for better code reliability

## Tracked Metrics

The tool monitors four key rating categories:
- **Overall Rating** (1-5 stars)
- **Staffing Rating** (1-5 stars)
- **Quality Measures Rating** (1-5 stars)
- **Health Inspection Rating** (1-5 stars)

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup

1. Clone or download the repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Make the script executable (optional):
```bash
chmod +x track_cms_star_rating_change.py
```

## Quick Start

### Basic Usage

Track specific CCN numbers:
```bash
python track_cms_star_rating_change.py --ccn 455682 675791 676336
```

### Using a Watchlist File

Create a file with CCN numbers (one per line):
```bash
echo "455682" > watchlist.txt
echo "675791" >> watchlist.txt
echo "676336" >> watchlist.txt
```

Run the tracker:
```bash
python track_cms_star_rating_change.py --ccn-file watchlist.txt
```

## Advanced Usage

### Enable Trend Analysis

Show statistical summaries for the last 6 months:
```bash
python track_cms_star_rating_change.py --ccn 455682 --trends
```

### Export Changes to CSV

Create timestamped CSV files of detected changes:
```bash
python track_cms_star_rating_change.py --ccn 455682 --export-csv
```

### Disable Historical Tracking

Run without saving to the history file:
```bash
python track_cms_star_rating_change.py --ccn 455682 --no-history
```

### Enable Notifications

Configure email/webhook alerts (requires config file):
```bash
python track_cms_star_rating_change.py --ccn 455682 --send-alerts --config config.json
```

### Adjust Logging Verbosity

Verbose mode (debug logging):
```bash
python track_cms_star_rating_change.py --ccn 455682 -v
```

Quiet mode (warnings and errors only):
```bash
python track_cms_star_rating_change.py --ccn 455682 -q
```

## Configuration

### Configuration File

Create a `config.json` file to enable notifications:

```json
{
  "email": {
    "enabled": true,
    "from": "alerts@example.com",
    "to": ["you@example.com"],
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "your_email@gmail.com",
    "smtp_password": "your_app_password"
  },
  "webhook": {
    "enabled": true,
    "url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  }
}
```

See `config.example.json` for a template.

### Email Setup (Gmail Example)

1. Enable 2-factor authentication on your Google account
2. Generate an App Password:
   - Go to Google Account Settings > Security > 2-Step Verification > App Passwords
   - Generate a new app password for "Mail"
3. Use the app password in your config file

### Webhook Setup (Slack Example)

1. Create a Slack Incoming Webhook:
   - Go to your Slack workspace settings
   - Navigate to Apps > Incoming Webhooks
   - Create a new webhook and copy the URL
2. Add the webhook URL to your config file

## Output Examples

### Console Output

```
================================================================================
RATING CHANGES DETECTED: 1
================================================================================

Example Nursing Home (CCN 455682) - Springfield, IL [2024-03-01]
  Changes: Overall: 3→4 ↑; Staffing: 4→5 ↑
```

### Trend Analysis Output

```
================================================================================
TREND ANALYSIS (Last 6 Months)
================================================================================
CCN     Provider              City        State  Data Points  Overall (Current)  Overall (Avg)  ...
455682  Example Nursing Home  Springfield IL     6            4                  3.67           ...
```

### Logging Output

```
2024-03-15 10:30:45 - INFO - Tracking 3 providers: 455682, 675791, 676336
2024-03-15 10:30:45 - INFO - Fetching data for 3 providers from CMS API...
2024-03-15 10:30:47 - INFO - Retrieved 24 records
2024-03-15 10:30:47 - INFO - Normalized data: 24 valid records
2024-03-15 10:30:47 - INFO - Detected changes for Example Nursing Home (CCN 455682)
2024-03-15 10:30:47 - INFO - Saved 24 records to cms_rating_history.csv
```

## Command-Line Options

### Required Arguments (choose one)
- `--ccn CCN [CCN ...]` - Provider CCN numbers to track
- `--ccn-file PATH` - File containing CCN numbers (one per line)

### Optional Arguments
- `--export-csv` - Export changes to timestamped CSV file
- `--trends` - Show trend analysis for tracked providers
- `--no-history` - Don't save to historical tracking file
- `--send-alerts` - Send email/webhook notifications for changes
- `--config PATH` - Path to JSON configuration file
- `--history-file PATH` - Custom path to history CSV file
- `-v, --verbose` - Enable verbose (debug) logging
- `-q, --quiet` - Only show warnings and errors
- `-h, --help` - Show help message

## Files Created

- **cms_tracker.log** - Application log file
- **cms_rating_history.csv** - Historical tracking database
- **cms_rating_changes_YYYYMMDD_HHMMSS.csv** - Exported change reports (when using --export-csv)

## Automation

### Using Cron (Linux/Mac)

Run daily at 8 AM:
```bash
0 8 * * * cd /path/to/script && python track_cms_star_rating_change.py --ccn-file watchlist.txt --send-alerts --config config.json
```

### Using Task Scheduler (Windows)

1. Open Task Scheduler
2. Create a new task
3. Set trigger (e.g., daily at 8 AM)
4. Set action: `python C:\path\to\track_cms_star_rating_change.py --ccn-file watchlist.txt`

## Troubleshooting

### No data returned
- Verify CCN numbers are correct
- Check CMS API availability: https://data.cms.gov
- Enable verbose logging with `-v` flag

### Email not sending
- Verify SMTP credentials in config file
- Check if app passwords are required (Gmail, Outlook, etc.)
- Review logs for specific error messages

### Import errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version: `python --version` (must be 3.8+)

## API Information

This tool uses the CMS Provider Information dataset:
- **Endpoint**: https://data.cms.gov/resource/4pq5-n9py.json
- **Documentation**: https://data.cms.gov
- **Data Source**: Centers for Medicare & Medicaid Services
- **Update Frequency**: Monthly

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with proper documentation
4. Test thoroughly
5. Submit a pull request

## License

MIT License - feel free to use and modify for your needs.

## Support

For issues, questions, or feature requests:
- Review the troubleshooting section above
- Check the log file (`cms_tracker.log`) for detailed error messages
- Enable verbose logging (`-v`) for debugging

## Changelog

### Version 2.0 (Current)
- Complete rewrite with object-oriented design
- Added historical tracking and trend analysis
- Email and webhook notification support
- Comprehensive error handling and logging
- CLI argument parsing with multiple options
- Type hints for better code reliability
- Automated retry logic for API requests
- CSV export functionality

### Version 1.0
- Basic rating change detection
- Simple console output
- Hardcoded CCN list
