# Quick Start Guide - CMS Star Rating Tracker

## TL;DR - Get Running in 30 Seconds

```bash
# Method 1: Using the wrapper script (easiest)
./run_tracker.sh --ccn 455682 675791 676336

# Method 2: Manual
source .venv/bin/activate
pip install -r requirements.txt
python track_cms_star_rating_change.py --ccn 455682 675791 676336
```

## What This Tool Does

Monitors CMS nursing home star ratings and alerts you when ratings change:
- Overall Rating (1-5 stars)
- Staffing Rating
- Quality Measures Rating
- Health Inspection Rating

## First Run Setup

### Option A: Easy Mode (Recommended)
```bash
./run_tracker.sh --ccn 455682 675791 676336
```

The wrapper script automatically:
- ✓ Creates virtual environment
- ✓ Installs dependencies
- ✓ Runs the tracker

### Option B: Manual Setup
```bash
# 1. Create virtual environment
python3 -m venv .venv

# 2. Activate it
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run tracker
python track_cms_star_rating_change.py --ccn 455682 675791 676336
```

## Common Use Cases

### Track Specific Facilities
```bash
./run_tracker.sh --ccn 455682 675791 676336
```

### Use a Watchlist File
```bash
# Create watchlist.txt with one CCN per line
echo "455682" > my_watchlist.txt
echo "675791" >> my_watchlist.txt
echo "676336" >> my_watchlist.txt

# Run with watchlist
./run_tracker.sh --ccn-file my_watchlist.txt
```

### Show Trend Analysis
```bash
./run_tracker.sh --ccn 455682 --trends
```

### Export Results to CSV
```bash
./run_tracker.sh --ccn 455682 --export-csv
```

### Enable Email/Webhook Alerts
```bash
# 1. Copy example config
cp config.example.json config.json

# 2. Edit config.json with your settings

# 3. Run with alerts
./run_tracker.sh --ccn 455682 --send-alerts --config config.json
```

### Verbose Mode (for debugging)
```bash
./run_tracker.sh --ccn 455682 -v
```

## Understanding the Output

### First Run
```
No rating changes detected.
```
This is normal! You need at least 2 data points to detect changes.

### After CMS Updates (Next Month)
```
================================================================================
RATING CHANGES DETECTED: 1
================================================================================

Example Nursing Home (CCN 455682) - Springfield, IL [2024-03-01]
  Changes: Overall: 3→4 ↑; Staffing: 4→5 ↑
```

## Important Files

- **cms_rating_history.csv** - Your historical tracking database (DON'T DELETE!)
- **cms_tracker.log** - Detailed logs for troubleshooting
- **config.json** - Your notification settings (optional)
- **watchlist.txt** - Your CCN list (optional)

## Scheduling Automatic Runs

### Mac/Linux (cron)
```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 8 AM)
0 8 * * * cd /path/to/discharge_planning && ./run_tracker.sh --ccn-file watchlist.txt --send-alerts
```

### Windows (Task Scheduler)
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger: Daily at 8:00 AM
4. Set action: Run program
   - Program: `C:\Python312\python.exe`
   - Arguments: `track_cms_star_rating_change.py --ccn-file watchlist.txt`
   - Start in: `C:\path\to\discharge_planning`

## Troubleshooting

### "command not found: python" or "ModuleNotFoundError"
**Fix**: Activate your virtual environment
```bash
source .venv/bin/activate
```

### "410 Client Error: Gone"
**Fix**: You're using the old version. The script has been updated - make sure you have the latest version.

### No changes detected (after multiple runs)
**Possible reasons**:
1. No ratings have actually changed (most common)
2. CMS hasn't updated their data yet
3. History file was deleted (need to rebuild history)

Enable verbose mode to see what's happening:
```bash
./run_tracker.sh --ccn 455682 -v
```

### Script takes a long time
**Normal behavior**: Downloads ~15-20MB CSV file, takes 30-60 seconds.

## Getting Help

1. **Full documentation**: See `README_CMS_TRACKER.md`
2. **Migration guide**: See `MIGRATION_NOTES.md`
3. **Check logs**: `cat cms_tracker.log`
4. **Test metadata API**: `python test_metadata.py`

## All Command-Line Options

```bash
python track_cms_star_rating_change.py [OPTIONS]

Required (choose one):
  --ccn CCN [CCN ...]       Provider CCN numbers
  --ccn-file PATH           File with CCN numbers

Optional:
  --export-csv              Export changes to CSV
  --trends                  Show trend analysis
  --no-history              Don't save to history file
  --send-alerts             Send email/webhook alerts
  --config PATH             JSON config file
  --history-file PATH       Custom history file path
  -v, --verbose             Verbose logging
  -q, --quiet               Quiet mode
  -h, --help                Show help
```

## What's New in v2.0

✨ **Major Improvements**:
- Fixed deprecated API (410 error)
- Object-oriented design
- Email and webhook notifications
- Trend analysis over 6 months
- CSV export functionality
- Comprehensive logging
- Better error handling
- Type hints throughout

📊 **Better Output**:
- Visual direction indicators (↑/↓)
- Formatted reports
- Statistical summaries

🔧 **More Flexible**:
- CLI arguments for everything
- Config files for settings
- Watchlist files for CCNs

## Pro Tips

1. **Run monthly** after CMS updates (usually 1st of month)
2. **Keep history file** - it's your change tracking database
3. **Use watchlist files** for easier management
4. **Enable verbose mode** when troubleshooting
5. **Set up cron/scheduled task** for automatic monitoring
6. **Use email alerts** to stay notified automatically

---

**Ready to start?**

```bash
./run_tracker.sh --ccn 455682 675791 676336
```

That's it! 🚀
