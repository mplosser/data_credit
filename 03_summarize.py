"""
Summarize output files: display file info, date ranges, and missing value analysis.
"""

from pathlib import Path
import pandas as pd

# Directory paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
RAW_DIR = DATA_DIR / 'raw'
PROCESSED_DIR = DATA_DIR / 'processed'


def summarize_file(filepath):
    """Summarize a single parquet file."""
    if not filepath.exists():
        print(f"  File not found: {filepath.name}")
        return

    df = pd.read_parquet(filepath)

    # Basic info
    print(f"\n  {filepath.name}")
    print(f"    Rows: {len(df):,}")
    print(f"    Columns: {len(df.columns)}")

    # Date range
    date_cols = [c for c in df.columns if 'date' in c.lower()]
    if date_cols:
        date_col = date_cols[0]
        if df[date_col].dtype == 'object':
            dates = pd.to_datetime(df[date_col], errors='coerce')
        else:
            dates = df[date_col]
        if dates.notna().any():
            print(f"    Date range: {dates.min()} to {dates.max()}")

    # Missing values summary
    numeric_cols = df.select_dtypes(include=['number']).columns
    if len(numeric_cols) > 0:
        missing_pct = (df[numeric_cols].isna().sum() / len(df) * 100).round(1)
        cols_with_missing = missing_pct[missing_pct > 0]
        if len(cols_with_missing) > 0:
            print(f"    Columns with missing values: {len(cols_with_missing)}")
            if len(cols_with_missing) <= 5:
                for col, pct in cols_with_missing.items():
                    print(f"      {col}: {pct}%")


def main():
    """Summarize all output files."""
    print("=" * 70)
    print("OUTPUT FILE SUMMARY")
    print("=" * 70)

    # Raw data
    print("\nRAW DATA:")
    raw_files = list(RAW_DIR.glob('*.parquet'))
    if raw_files:
        for f in raw_files:
            summarize_file(f)
    else:
        print("  No raw parquet files found")

    # Processed data - Rating
    print("\n\nPROCESSED DATA - Corporate Credit Ratings:")
    for freq in ['daily', 'monthly', 'quarterly', 'quarterly_avg']:
        summarize_file(PROCESSED_DIR / f'{freq}_rating.parquet')

    # Processed data - HQM Curve
    print("\n\nPROCESSED DATA - HQM Curve:")
    for freq in ['monthly_curve_end', 'quarterly_curve_end', 'monthly_curve_avg', 'quarterly_curve_avg']:
        summarize_file(PROCESSED_DIR / f'{freq}.parquet')

    # Processed data - Mortgage Rates
    print("\n\nPROCESSED DATA - Mortgage Rates:")
    for freq in ['weekly', 'monthly', 'quarterly', 'quarterly_avg']:
        summarize_file(PROCESSED_DIR / f'{freq}_mtgrates.parquet')

    print("\n" + "=" * 70)
    print("SUMMARY COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
