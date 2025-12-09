"""
Download corporate credit yields, spreads, HQM curve, and mortgage rates from FRED and Treasury.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import requests
from fredapi import Fred

# Load environment variables
load_dotenv()

# Configuration
FRED_API_KEY = os.getenv('FRED_API_KEY')
if not FRED_API_KEY:
    raise ValueError("FRED_API_KEY not found. Please set it in .env file.")

# Directory paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
RAW_DIR = DATA_DIR / 'raw'

# Create directories if they don't exist
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Initialize FRED API
fred = Fred(api_key=FRED_API_KEY)
print("FRED API initialized successfully")


def download_fred_series():
    """Download corporate spreads and yields from FRED."""
    print("\nDownloading corporate spreads and yields from FRED...\n")

    # Corporate credit series
    spread_series = [
        # ICE BofA Corporate Bond Spreads
        'BAMLC0A1CAAA',      # AAA Spread
        'BAMLC0A1CAAAEY',    # AAA Effective Yield
        'BAMLC0A2CAA',       # AA Spread
        'BAMLC0A2CAAEY',     # AA Effective Yield
        'BAMLC0A3CA',        # A Spread
        'BAMLC0A3CAEY',      # A Effective Yield
        'BAMLC0A4CBBB',      # BBB Spread
        'BAMLC0A4CBBBEY',    # BBB Effective Yield
        'BAMLH0A1HYBB',      # High Yield BB Spread
        'BAMLH0A1HYBBEY',    # High Yield BB Effective Yield
        'BAMLH0A2HYB',       # High Yield B Spread
        'BAMLH0A2HYBEY',     # High Yield B Effective Yield
    ]

    # HQM Corporate Bond indices (zero-coupon)
    hqm_series = [
        'HQMCB6MT', 'HQMCB1YR', 'HQMCB2YR', 'HQMCB3YR', 'HQMCB5YR',
        'HQMCB10YR', 'HQMCB15YR', 'HQMCB20YR', 'HQMCB30YR',
    ]

    # HQM Par yields
    hqm_par_series = [
        'HQMCB2YRP', 'HQMCB5YRP', 'HQMCB10YRP', 'HQMCB30YRP',
    ]

    # Mortgage rates
    mortgage_series = [
        'MORTGAGE30US',      # 30-Year Fixed Rate Mortgage Average
        'MORTGAGE15US',      # 15-Year Fixed Rate Mortgage Average
        'OBMMIJUMBO30YF',    # 30-Year Jumbo Mortgage Rate
    ]

    all_series = spread_series + hqm_series + hqm_par_series + mortgage_series

    # Download data
    data_dict = {}
    for series in all_series:
        try:
            print(f"  Downloading {series}...")
            data_dict[series] = fred.get_series(series, observation_start='1980-01-01')
        except Exception as e:
            print(f"  Warning: Could not download {series}: {e}")

    # Combine into DataFrame
    df = pd.DataFrame(data_dict)
    df.index.name = 'date'
    df = df.reset_index()

    # Save to raw directory
    output_path = RAW_DIR / 'fred_data.parquet'
    df.to_parquet(output_path)
    print(f"\nSaved FRED data to {output_path}")
    print(f"Shape: {df.shape}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")

    return df


def download_hqm_curve():
    """Download HQM Corporate Credit Curve from Treasury website."""
    print("\nDownloading HQM Corporate Credit Curve from Treasury...\n")

    # Treasury HQM curve URLs
    urls = {
        'end_of_month': 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_hqm_yield_curve&field_tdr_date_value_month=202501',
        'monthly_avg': 'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_hqm_yield_curve&field_tdr_date_value_month=202501',
    }

    # Note: The Treasury website structure may require different parsing
    # For now, we'll use the FRED HQM series as the primary source
    print("  Note: HQM curve data is sourced from FRED series (HQMCB*)")
    print("  Treasury website data can be added as supplementary source")


def main():
    """Run all download tasks."""
    print("=" * 70)
    print("DOWNLOADING DATA FROM FRED AND TREASURY")
    print("=" * 70)

    # Download from FRED
    df_fred = download_fred_series()

    # Download HQM curve from Treasury (supplementary)
    download_hqm_curve()

    print("\n" + "=" * 70)
    print("DOWNLOAD COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
