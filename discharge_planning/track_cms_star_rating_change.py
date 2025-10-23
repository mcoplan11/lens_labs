#!/usr/bin/env python3
"""
CMS Star Rating Tracker

Monitors CMS nursing home star ratings and alerts on changes.
Tracks overall, staffing, quality measures, and health inspection ratings.

Author: Mitchell Coplan
License: MIT
"""

import argparse
import json
import logging
import smtplib
import sys
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('cms_tracker.log')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class RatingChange:
    """Represents a rating change for a provider."""
    ccn: str
    provider_name: str
    city: str
    state: str
    as_of_date: str
    changes: List[str]
    previous_date: str

    def __str__(self) -> str:
        """Format rating change as a readable string."""
        return (
            f"{self.provider_name} (CCN {self.ccn}) - "
            f"{self.city}, {self.state} [{self.as_of_date}]\n"
            f"  Changes: {'; '.join(self.changes)}"
        )


class CMSStarRatingTracker:
    """Tracks CMS star ratings for nursing homes."""

    # CMS now provides data as CSV files instead of Socrata API
    DATASET_ID = "4pq5-n9py"
    METADATA_URL = f"https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/{DATASET_ID}"

    RATING_FIELDS = [
        "overall_rating",
        "staffing_rating",
        "quality_measures_rating",
        "health_inspection_rating"
    ]
    RATING_LABELS = {
        "overall_rating": "Overall",
        "staffing_rating": "Staffing",
        "quality_measures_rating": "Quality Measures",
        "health_inspection_rating": "Health Inspection"
    }

    def __init__(
        self,
        ccns: List[str],
        history_file: Optional[Path] = None,
        config_file: Optional[Path] = None
    ):
        """
        Initialize the CMS Star Rating Tracker.

        Args:
            ccns: List of CCN provider numbers to track
            history_file: Path to CSV file for historical tracking
            config_file: Path to JSON config file
        """
        self.ccns = ccns
        self.history_file = history_file or Path("cms_rating_history.csv")
        self.config = self._load_config(config_file)
        self.session = self._create_session()

    def _load_config(self, config_file: Optional[Path]) -> Dict:
        """Load configuration from JSON file."""
        if config_file and config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load config file: {e}")
        return {}

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _get_latest_csv_url(self) -> str:
        """
        Get the latest CSV download URL from CMS metadata API.

        Returns:
            URL to the latest CSV file

        Raises:
            requests.RequestException: If metadata request fails
            ValueError: If no CSV URL found in metadata
        """
        try:
            logger.info("Fetching latest dataset metadata from CMS...")
            response = self.session.get(self.METADATA_URL, timeout=30)
            response.raise_for_status()

            metadata = response.json()

            # Extract CSV download URL from distribution section
            distributions = metadata.get("distribution", [])
            for dist in distributions:
                if dist.get("mediaType") == "text/csv":
                    url = dist.get("downloadURL")
                    if url:
                        logger.info(f"Found CSV URL: {url}")
                        return url

            raise ValueError("No CSV download URL found in metadata")

        except requests.RequestException as e:
            logger.error(f"Failed to fetch metadata: {e}")
            raise
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to parse metadata: {e}")
            raise

    def fetch_data(self) -> pd.DataFrame:
        """
        Fetch rating data from CMS CSV file.

        Returns:
            DataFrame with provider rating data

        Raises:
            requests.RequestException: If CSV download fails
        """
        try:
            # Get the latest CSV URL dynamically
            csv_url = self._get_latest_csv_url()

            logger.info(f"Downloading provider data CSV...")
            response = self.session.get(csv_url, timeout=120)
            response.raise_for_status()

            # Read CSV directly from response content
            from io import StringIO
            df = pd.read_csv(StringIO(response.text), low_memory=False)

            logger.info(f"Downloaded CSV with {len(df)} total records")

            # Filter to only our CCNs
            if df.empty:
                logger.warning("No data in CSV file")
                return pd.DataFrame()

            # The CSV uses "CMS Certification Number (CCN)" as the provider number column
            ccn_column = "CMS Certification Number (CCN)"
            if ccn_column in df.columns:
                df = df[df[ccn_column].astype(str).str.zfill(6).isin(self.ccns)]
            else:
                logger.error(f"Could not find provider number column in CSV. Available columns: {list(df.columns[:10])}...")
                raise ValueError("Provider number column not found")

            logger.info(f"Filtered to {len(df)} records for tracked providers")

            return df

        except requests.RequestException as e:
            logger.error(f"Failed to fetch data from CMS: {e}")
            raise

    def normalize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize and clean the dataframe.

        Args:
            df: Raw dataframe from CSV

        Returns:
            Cleaned dataframe with proper types
        """
        if df.empty:
            return df

        # Map CSV column names to our internal names
        # Based on actual CMS CSV structure (as of 2025)
        column_mapping = {
            "CMS Certification Number (CCN)": "federal_provider_number",
            "Provider Name": "provider_name",
            "City/Town": "city",
            "State": "state",
            "Overall Rating": "overall_rating",
            "Health Inspection Rating": "health_inspection_rating",
            "QM Rating": "quality_measures_rating",
            "Staffing Rating": "staffing_rating",
            "Processing Date": "month_year"
        }

        # Rename columns if they exist
        rename_dict = {}
        for old_name, new_name in column_mapping.items():
            if old_name in df.columns:
                rename_dict[old_name] = new_name

        df = df.rename(columns=rename_dict)

        # Normalize CCN
        if "federal_provider_number" in df.columns:
            df["ccn"] = df["federal_provider_number"].astype(str).str.zfill(6)
        else:
            logger.error("federal_provider_number column not found after mapping")
            return pd.DataFrame()

        # Parse dates - the CSV has a single processing date, not historical month_year
        # We'll use processing date as the snapshot date
        if "month_year" in df.columns:
            df["month_year"] = pd.to_datetime(df["month_year"], errors="coerce")
        else:
            # If no date column, use current date
            logger.warning("No date column found, using current date")
            df["month_year"] = pd.Timestamp.now()

        df = df.dropna(subset=["month_year"])

        # Convert ratings to numeric
        for col in self.RATING_FIELDS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            else:
                logger.warning(f"Column {col} not found in data")
                df[col] = pd.NA

        # Sort by CCN and date
        df = df.sort_values(["ccn", "month_year"])

        logger.info(f"Normalized data: {len(df)} valid records")
        return df

    def detect_changes(
        self,
        df: pd.DataFrame,
        lookback_periods: int = 2
    ) -> List[RatingChange]:
        """
        Detect rating changes by comparing recent periods.

        Args:
            df: Normalized dataframe
            lookback_periods: Number of periods to compare (default: 2)

        Returns:
            List of RatingChange objects
        """
        changes = []

        for ccn, group in df.groupby("ccn"):
            sorted_group = group.sort_values("month_year")
            tail = sorted_group.tail(lookback_periods)

            if len(tail) < 2:
                logger.debug(f"CCN {ccn}: Not enough data (only {len(tail)} periods)")
                continue

            previous = tail.iloc[-2]
            current = tail.iloc[-1]

            detected_changes = []
            for rating_col, label in self.RATING_LABELS.items():
                old_val = previous[rating_col]
                new_val = current[rating_col]

                if pd.notna(old_val) and pd.notna(new_val) and old_val != new_val:
                    direction = "↑" if new_val > old_val else "↓"
                    change_str = f"{label}: {int(old_val)}→{int(new_val)} {direction}"
                    detected_changes.append(change_str)

            if detected_changes:
                change = RatingChange(
                    ccn=current["ccn"],
                    provider_name=current["provider_name"],
                    city=current["city"],
                    state=current["state"],
                    as_of_date=current["month_year"].date().isoformat(),
                    previous_date=previous["month_year"].date().isoformat(),
                    changes=detected_changes
                )
                changes.append(change)
                logger.info(f"Detected changes for {current['provider_name']} (CCN {ccn})")

        return changes

    def save_to_history(self, df: pd.DataFrame) -> None:
        """
        Save current data to historical CSV file.

        Args:
            df: DataFrame to save
        """
        try:
            # Load existing history if it exists
            if self.history_file.exists():
                history_df = pd.read_csv(self.history_file)
                history_df["month_year"] = pd.to_datetime(history_df["month_year"])

                # Merge with new data, avoiding duplicates
                combined = pd.concat([history_df, df], ignore_index=True)
                combined = combined.drop_duplicates(
                    subset=["ccn", "month_year"],
                    keep="last"
                )
            else:
                combined = df

            # Save to CSV
            combined.to_csv(self.history_file, index=False)
            logger.info(f"Saved {len(combined)} records to {self.history_file}")

        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def get_trend_summary(self, df: pd.DataFrame, months: int = 6) -> pd.DataFrame:
        """
        Get trend summary for the specified number of months.

        Args:
            df: Normalized dataframe
            months: Number of months to analyze

        Returns:
            DataFrame with trend statistics
        """
        cutoff_date = datetime.now() - timedelta(days=months * 30)
        recent_df = df[df["month_year"] >= cutoff_date]

        if recent_df.empty:
            return pd.DataFrame()

        # Calculate statistics per provider
        summary_data = []
        for ccn, group in recent_df.groupby("ccn"):
            sorted_group = group.sort_values("month_year")
            latest = sorted_group.iloc[-1]

            stats = {
                "CCN": ccn,
                "Provider": latest["provider_name"],
                "City": latest["city"],
                "State": latest["state"],
                "Data Points": len(sorted_group)
            }

            for rating_col, label in self.RATING_LABELS.items():
                values = sorted_group[rating_col].dropna()
                if len(values) > 0:
                    stats[f"{label} (Current)"] = int(latest[rating_col]) if pd.notna(latest[rating_col]) else "N/A"
                    stats[f"{label} (Avg)"] = round(values.mean(), 2)
                    stats[f"{label} (Min)"] = int(values.min())
                    stats[f"{label} (Max)"] = int(values.max())

            summary_data.append(stats)

        return pd.DataFrame(summary_data)

    def send_email_alert(self, changes: List[RatingChange]) -> None:
        """
        Send email notification for rating changes.

        Args:
            changes: List of rating changes to report
        """
        if not changes:
            return

        email_config = self.config.get("email", {})
        if not email_config.get("enabled"):
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = email_config["from"]
            msg["To"] = ", ".join(email_config["to"])
            msg["Subject"] = f"CMS Star Rating Alert: {len(changes)} Change(s) Detected"

            body = "CMS Star Rating Changes Detected:\n\n"
            body += "\n\n".join(str(change) for change in changes)

            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(email_config["smtp_host"], email_config.get("smtp_port", 587)) as server:
                server.starttls()
                if email_config.get("smtp_user"):
                    server.login(email_config["smtp_user"], email_config["smtp_password"])
                server.send_message(msg)

            logger.info(f"Email alert sent to {email_config['to']}")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

    def send_webhook_alert(self, changes: List[RatingChange]) -> None:
        """
        Send webhook notification for rating changes.

        Args:
            changes: List of rating changes to report
        """
        if not changes:
            return

        webhook_config = self.config.get("webhook", {})
        if not webhook_config.get("enabled"):
            return

        try:
            payload = {
                "timestamp": datetime.now().isoformat(),
                "changes": [asdict(change) for change in changes]
            }

            response = self.session.post(
                webhook_config["url"],
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            logger.info(f"Webhook alert sent to {webhook_config['url']}")

        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")

    def run(
        self,
        save_history: bool = True,
        export_csv: bool = False,
        show_trends: bool = False,
        send_alerts: bool = False
    ) -> List[RatingChange]:
        """
        Run the tracker and detect changes.

        Args:
            save_history: Whether to save data to history file
            export_csv: Whether to export changes to CSV
            show_trends: Whether to show trend analysis
            send_alerts: Whether to send notifications

        Returns:
            List of detected rating changes
        """
        try:
            # Fetch and process data
            df = self.fetch_data()
            if df.empty:
                logger.warning("No data to process")
                return []

            df = self.normalize_data(df)

            # Save history if requested
            if save_history:
                self.save_to_history(df)

            # Detect changes
            changes = self.detect_changes(df)

            # Export changes if requested
            if export_csv and changes:
                self.export_changes_to_csv(changes)

            # Show trends if requested
            if show_trends:
                trends = self.get_trend_summary(df)
                if not trends.empty:
                    print("\n" + "="*80)
                    print("TREND ANALYSIS (Last 6 Months)")
                    print("="*80)
                    print(trends.to_string(index=False))

            # Send alerts if requested
            if send_alerts:
                self.send_email_alert(changes)
                self.send_webhook_alert(changes)

            return changes

        except Exception as e:
            logger.error(f"Error running tracker: {e}")
            raise

    def export_changes_to_csv(self, changes: List[RatingChange]) -> None:
        """
        Export changes to a CSV file.

        Args:
            changes: List of rating changes
        """
        if not changes:
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cms_rating_changes_{timestamp}.csv"

            df = pd.DataFrame([asdict(change) for change in changes])
            df.to_csv(filename, index=False)

            logger.info(f"Exported changes to {filename}")

        except Exception as e:
            logger.error(f"Failed to export changes: {e}")


def load_ccns_from_file(filepath: Path) -> List[str]:
    """
    Load CCNs from a text file (one per line).

    Args:
        filepath: Path to file containing CCNs

    Returns:
        List of CCN strings
    """
    try:
        with open(filepath, 'r') as f:
            ccns = [line.strip() for line in f if line.strip()]
        return ccns
    except Exception as e:
        logger.error(f"Failed to load CCNs from file: {e}")
        return []


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Track CMS star rating changes for nursing homes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --ccn 455682 675791 676336
  %(prog)s --ccn-file watchlist.txt --export-csv
  %(prog)s --ccn 455682 --trends --no-history
  %(prog)s --ccn 455682 --send-alerts --config config.json
        """
    )

    # CCN input options
    ccn_group = parser.add_mutually_exclusive_group(required=True)
    ccn_group.add_argument(
        "--ccn",
        nargs="+",
        help="Provider CCN numbers to track"
    )
    ccn_group.add_argument(
        "--ccn-file",
        type=Path,
        help="File containing CCN numbers (one per line)"
    )

    # Output options
    parser.add_argument(
        "--export-csv",
        action="store_true",
        help="Export changes to timestamped CSV file"
    )
    parser.add_argument(
        "--trends",
        action="store_true",
        help="Show trend analysis for tracked providers"
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Don't save to historical tracking file"
    )

    # Notification options
    parser.add_argument(
        "--send-alerts",
        action="store_true",
        help="Send email/webhook notifications for changes"
    )

    # Configuration
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to JSON configuration file"
    )
    parser.add_argument(
        "--history-file",
        type=Path,
        help="Path to history CSV file (default: cms_rating_history.csv)"
    )

    # Logging
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Only show warnings and errors"
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.WARNING)

    # Load CCNs
    if args.ccn:
        ccns = args.ccn
    else:
        ccns = load_ccns_from_file(args.ccn_file)
        if not ccns:
            logger.error("No CCNs loaded from file")
            sys.exit(1)

    logger.info(f"Tracking {len(ccns)} providers: {', '.join(ccns)}")

    # Create tracker
    tracker = CMSStarRatingTracker(
        ccns=ccns,
        history_file=args.history_file,
        config_file=args.config
    )

    # Run tracker
    try:
        changes = tracker.run(
            save_history=not args.no_history,
            export_csv=args.export_csv,
            show_trends=args.trends,
            send_alerts=args.send_alerts
        )

        # Display results
        if changes:
            print("\n" + "="*80)
            print(f"RATING CHANGES DETECTED: {len(changes)}")
            print("="*80 + "\n")
            for change in changes:
                print(change)
                print()
            logger.info(f"Detected {len(changes)} rating change(s)")
        else:
            print("\nNo rating changes detected.")
            logger.info("No rating changes detected")

        sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
