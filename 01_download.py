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

    # NEVER overwrite history. Since April 2026 FRED serves only the last three years of the
    # ICE BofA series, so a fresh pull is SHORTER than what we hold. Each pull is kept as its
    # own dated file, and merged into fred_data.parquet by appending only NEW dates: values we
    # already hold are never replaced, conflicts on overlapping dates are logged, and the
    # write is refused if any series would lose observations. The full history is also
    # archived (read-only) in OneDrive/bec_irreplaceable_data.
    pull_path = RAW_DIR / f"fred_pull_{pd.Timestamp.today():%Y%m%d}.parquet"
    df.to_parquet(pull_path)
    print(f"\n  Saved this pull as {pull_path.name}")
    output_path = RAW_DIR / 'fred_data.parquet'
    if output_path.exists():
        old = pd.read_parquet(output_path)
        old['date'] = pd.to_datetime(old['date'])
        df['date'] = pd.to_datetime(df['date'])
        merged = old.set_index('date').combine_first(df.set_index('date'))  # existing values win
        # log overlapping dates where the new pull disagrees with what we hold
        both = old.set_index('date').index.intersection(df.set_index('date').index)
        o, n = old.set_index('date').loc[both], df.set_index('date').loc[both]
        for c in [c for c in n.columns if c in o.columns]:
            d = (o[c] - n[c]).abs()
            k = int((d > 1e-9).sum())
            if k:
                print(f"  NOTE {c}: {k} overlapping dates differ from held values (max {d.max():.4f}); held values kept")
        lost = {c: int(old[c].notna().sum() - merged[c].notna().sum()) for c in old.columns if c != 'date' and c in merged}
        lost = {c: v for c, v in lost.items() if v > 0}
        if lost:
            raise RuntimeError(f"refusing to write {output_path.name}: series would lose observations {lost}")
        df = merged.reset_index()
        added = len(df) - len(old)
        print(f"  Merged into {output_path.name}: {added} new dates appended; history preserved")
    df.to_parquet(output_path)
    print(f"\nSaved FRED data to {output_path}")
    print(f"Shape: {df.shape}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")

    return df


GZ_URL = 'https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv'


def download_gz():
    """Download the Gilchrist-Zakrajsek credit spread and excess bond premium (Federal Reserve Board).

    Monthly from 1973, updated about monthly (FEDS Notes, "Updating the Recession Risk and the
    Excess Bond Premium"). The Board re-estimates the whole history each release, so the newest
    vintage is the series of record (raw/gz_ebp.parquet); every pull is also kept as a dated CSV.
    """
    print("\nDownloading Gilchrist-Zakrajsek spread and excess bond premium (Federal Reserve Board)...\n")
    response = requests.get(GZ_URL, timeout=60, headers={'User-Agent': 'data_credit'})
    response.raise_for_status()
    pull_path = RAW_DIR / f"gz_ebp_{pd.Timestamp.today():%Y%m%d}.csv"
    pull_path.write_bytes(response.content)
    df = pd.read_csv(pull_path)
    df['date'] = pd.to_datetime(df['date'])
    df.to_parquet(RAW_DIR / 'gz_ebp.parquet', index=False)
    print(f"  Saved {pull_path.name} and gz_ebp.parquet: {len(df)} months, "
          f"{df['date'].min():%Y-%m} to {df['date'].max():%Y-%m}")
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

    # Gilchrist-Zakrajsek spread and excess bond premium (Federal Reserve Board)
    download_gz()

    # Download HQM curve from Treasury (supplementary)
    download_hqm_curve()

    print("\n" + "=" * 70)
    print("DOWNLOAD COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
