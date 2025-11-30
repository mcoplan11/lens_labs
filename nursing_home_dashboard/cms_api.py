"""
CMS API Module
Handles data fetching and processing from CMS Provider Data API
"""

import requests
import pandas as pd
from typing import Dict, List, Optional
import json
from datetime import datetime, timedelta


class CMSAPI:
    """Interface for CMS Provider Data API"""

    BASE_URL = "https://data.cms.gov/provider-data/api/1/datastore/query"
    DATASET_ID = "4pq5-n9py"  # Nursing Homes Including Rehab Services

    def __init__(self):
        self.cache = {}
        self.cache_duration = timedelta(hours=1)

    def search_facilities(
        self,
        state: Optional[str] = None,
        search_term: Optional[str] = None,
        limit: int = 100
    ) -> pd.DataFrame:
        """
        Search for nursing facilities

        Args:
            state: Two-letter state code (e.g., 'CA')
            search_term: Search term for facility name, city, or ZIP
            limit: Maximum number of results

        Returns:
            DataFrame with facility data
        """
        # Check cache
        cache_key = f"{state}_{search_term}_{limit}"
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_duration:
                print("Returning cached data")
                return cached_data

        try:
            # Fetch data in batches if we need a specific state
            # CMS API returns facilities alphabetically by state
            all_facilities = []
            batch_size = 1000
            max_batches = 20 if state else 2  # Fetch more batches if filtering by state

            for batch in range(max_batches):
                query = {
                    "limit": batch_size,
                    "offset": batch * batch_size
                }

                url = f"{self.BASE_URL}/{self.DATASET_ID}/0"
                response = requests.post(
                    url,
                    json=query,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get('results', [])

                    if not results:
                        break  # No more data

                    all_facilities.extend(results)

                    # If we have a state filter and found enough facilities from that state, stop
                    if state:
                        df_temp = self._process_data({'results': all_facilities})
                        state_count = len(df_temp[df_temp['state'] == state])
                        if state_count >= limit:
                            break
                else:
                    print(f"API Error: {response.status_code}")
                    return self._get_sample_data()

            # Process all fetched data
            df = self._process_data({'results': all_facilities})

            # Apply state filter client-side
            if state and not df.empty:
                df = df[df['state'] == state]

            # Apply search filter if provided
            if search_term and not df.empty:
                df = self._filter_by_search(df, search_term)

            # Limit results after filtering
            if len(df) > limit:
                df = df.head(limit)

            # Cache the results
            self.cache[cache_key] = (datetime.now(), df)

            return df

        except Exception as e:
            print(f"Error fetching data: {e}")
            return self._get_sample_data()

    def _process_data(self, raw_data: dict) -> pd.DataFrame:
        """Process raw API data into clean DataFrame"""
        results = raw_data.get('results', [])

        if not results:
            return pd.DataFrame()

        processed = []
        for facility in results:
            processed.append({
                'id': facility.get('cms_certification_number_ccn', 'Unknown'),
                'name': facility.get('provider_name', 'Unknown'),
                'address': facility.get('provider_address', ''),
                'city': facility.get('citytown', ''),
                'state': facility.get('state', ''),
                'zip': facility.get('zip_code', ''),
                'phone': facility.get('provider_phone_number', ''),

                # Ratings
                'overall_rating': self._parse_rating(facility.get('overall_rating')),
                'health_rating': self._parse_rating(facility.get('health_inspection_rating')),
                'staffing_rating': self._parse_rating(facility.get('staffing_rating')),
                'quality_rating': self._parse_rating(facility.get('quality_measure_rating')),
                'rn_rating': self._parse_rating(facility.get('rn_staffing_rating')),

                # Facility info
                'ownership': facility.get('ownership_type', 'Unknown'),
                'bed_count': int(facility.get('number_of_certified_beds', 0) or 0),

                # Quality measures (percentages)
                'falls_with_injury': self._parse_float(facility.get('percentage_of_long_stay_residents_who_experienced_one_or_more_falls_with_major_injury')),
                'pressure_ulcers': self._parse_float(facility.get('percentage_of_high_risk_long_stay_residents_with_pressure_ulcers')),
                'uti_rate': self._parse_float(facility.get('percentage_of_long_stay_residents_with_a_urinary_tract_infection')),
                'antipsychotic_use': self._parse_float(facility.get('percentage_of_long_stay_residents_receiving_an_antipsychotic_medication')),

                # Staffing metrics
                'rn_hours_per_day': self._parse_float(facility.get('registered_nurse_staffing_hours_per_resident_per_day')),
                'total_hours_per_day': self._parse_float(facility.get('total_nurse_staffing_hours_per_resident_per_day')),

                # Inspection
                'health_deficiencies': int(facility.get('number_of_facility_reported_incidents', 0) or 0),
                'fire_deficiencies': int(facility.get('number_of_fire_safety_deficiencies', 0) or 0),

                # Location
                'latitude': self._parse_float(facility.get('provider_latitude')),
                'longitude': self._parse_float(facility.get('provider_longitude')),
            })

        return pd.DataFrame(processed)

    def _parse_rating(self, value) -> int:
        """Parse rating value (1-5 or 0 for not rated)"""
        if not value or value == 'Not Available':
            return 0
        try:
            rating = int(value)
            return max(0, min(rating, 5))  # Clamp between 0 and 5
        except (ValueError, TypeError):
            return 0

    def _parse_float(self, value) -> Optional[float]:
        """Parse float value"""
        if not value or value == 'Not Available':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _filter_by_search(self, df: pd.DataFrame, search_term: str) -> pd.DataFrame:
        """Filter DataFrame by search term"""
        term = search_term.lower().strip()

        mask = (
            df['name'].str.lower().str.contains(term, na=False) |
            df['city'].str.lower().str.contains(term, na=False) |
            df['zip'].str.contains(term, na=False) |
            df['address'].str.lower().str.contains(term, na=False)
        )

        return df[mask]

    def _get_sample_data(self) -> pd.DataFrame:
        """Return sample data for demo purposes"""
        sample_data = [
            {
                'id': '105001',
                'name': 'Sunshine Senior Living Center',
                'address': '123 Main Street',
                'city': 'Los Angeles',
                'state': 'CA',
                'zip': '90001',
                'phone': '(555) 123-4567',
                'overall_rating': 5,
                'health_rating': 5,
                'staffing_rating': 4,
                'quality_rating': 5,
                'rn_rating': 5,
                'ownership': 'Non profit',
                'bed_count': 120,
                'falls_with_injury': 2.1,
                'pressure_ulcers': 1.5,
                'uti_rate': 3.2,
                'antipsychotic_use': 8.5,
                'rn_hours_per_day': 0.8,
                'total_hours_per_day': 4.2,
                'health_deficiencies': 2,
                'fire_deficiencies': 0,
                'latitude': 34.0522,
                'longitude': -118.2437,
            },
            {
                'id': '105002',
                'name': 'Green Valley Nursing Home',
                'address': '456 Oak Avenue',
                'city': 'San Francisco',
                'state': 'CA',
                'zip': '94102',
                'phone': '(555) 234-5678',
                'overall_rating': 4,
                'health_rating': 4,
                'staffing_rating': 4,
                'quality_rating': 4,
                'rn_rating': 3,
                'ownership': 'For profit',
                'bed_count': 85,
                'falls_with_injury': 3.5,
                'pressure_ulcers': 2.1,
                'uti_rate': 4.8,
                'antipsychotic_use': 12.3,
                'rn_hours_per_day': 0.6,
                'total_hours_per_day': 3.8,
                'health_deficiencies': 5,
                'fire_deficiencies': 1,
                'latitude': 37.7749,
                'longitude': -122.4194,
            },
            {
                'id': '105003',
                'name': 'Maple Grove Care Center',
                'address': '789 Elm Street',
                'city': 'San Diego',
                'state': 'CA',
                'zip': '92101',
                'phone': '(555) 345-6789',
                'overall_rating': 3,
                'health_rating': 3,
                'staffing_rating': 3,
                'quality_rating': 3,
                'rn_rating': 2,
                'ownership': 'For profit',
                'bed_count': 150,
                'falls_with_injury': 5.2,
                'pressure_ulcers': 4.1,
                'uti_rate': 6.5,
                'antipsychotic_use': 15.8,
                'rn_hours_per_day': 0.5,
                'total_hours_per_day': 3.2,
                'health_deficiencies': 8,
                'fire_deficiencies': 2,
                'latitude': 32.7157,
                'longitude': -117.1611,
            },
            {
                'id': '105004',
                'name': 'Riverside Rehabilitation Center',
                'address': '321 River Road',
                'city': 'Sacramento',
                'state': 'CA',
                'zip': '95814',
                'phone': '(555) 456-7890',
                'overall_rating': 4,
                'health_rating': 5,
                'staffing_rating': 3,
                'quality_rating': 4,
                'rn_rating': 4,
                'ownership': 'Non profit',
                'bed_count': 95,
                'falls_with_injury': 2.8,
                'pressure_ulcers': 1.9,
                'uti_rate': 3.9,
                'antipsychotic_use': 9.2,
                'rn_hours_per_day': 0.7,
                'total_hours_per_day': 3.9,
                'health_deficiencies': 3,
                'fire_deficiencies': 0,
                'latitude': 38.5816,
                'longitude': -121.4944,
            },
        ]

        return pd.DataFrame(sample_data)

    def clear_cache(self):
        """Clear all cached data"""
        self.cache = {}
        print("Cache cleared")
