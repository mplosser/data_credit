"""
Summarize output files: display file info, date ranges, and column availability.
"""

from collections import defaultdict
from pathlib import Path
import pandas as pd

# Directory paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
RAW_DIR = DATA_DIR / 'raw'
PROCESSED_DIR = DATA_DIR / 'processed'


def get_date_col(df):
    """Get the primary date column from dataframe."""
    for col in ['daten', 'datem', 'dateq']:
        if col in df.columns:
            return col
    date_cols = [c for c in df.columns if 'date' in c.lower()]
    return date_cols[0] if date_cols else None


def format_date(val):
    """Format date value for display."""
    if pd.isna(val):
        return 'N/A'
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d')
    return str(val)


def summarize_file(filepath):
    """Summarize a single parquet file with column availability details."""
    if not filepath.exists():
        print(f"  File not found: {filepath.name}")
        return

    df = pd.read_parquet(filepath)
    date_col = get_date_col(df)

    # Basic info
    print(f"\n  {filepath.name}")
    print(f"    Rows: {len(df):,}")
    print(f"    Columns: {len(df.columns)}")

    # Overall date range
    if date_col:
        if df[date_col].dtype == 'object':
            sorted_dates = df[date_col].dropna().sort_values()
            if len(sorted_dates) > 0:
                print(f"    Date range: {sorted_dates.iloc[0]} to {sorted_dates.iloc[-1]}")
        else:
            dates = df[date_col]
            if dates.notna().any():
                print(f"    Date range: {format_date(dates.min())} to {format_date(dates.max())}")

    # Column availability analysis - exclude pandas artifacts and date columns
    skip_cols = {'__index_level_0__', 'index', 'level_0'}
    date_related = {c for c in df.columns if 'date' in c.lower()}
    numeric_cols = [
        c for c in df.select_dtypes(include=['number']).columns
        if c not in skip_cols and not c.startswith('__') and c not in date_related
    ]
    if not numeric_cols or not date_col:
        return

    # Sort dataframe by date for proper range detection
    df_sorted = df.sort_values(date_col).reset_index(drop=True)

    # Collect column availability info
    col_info = []
    for col in numeric_cols:
        non_null_mask = df_sorted[col].notna()
        if non_null_mask.any():
            first_idx = non_null_mask.idxmax()
            last_idx = non_null_mask[::-1].idxmax()
            first_date = df_sorted.loc[first_idx, date_col]
            last_date = df_sorted.loc[last_idx, date_col]
            non_null_count = non_null_mask.sum()
            missing_pct = round((1 - non_null_count / len(df)) * 100, 1)
            col_info.append({
                'col': col,
                'first': first_date,
                'last': last_date,
                'count': non_null_count,
                'missing_pct': missing_pct
            })
        else:
            col_info.append({
                'col': col,
                'first': None,
                'last': None,
                'count': 0,
                'missing_pct': 100.0
            })

    # Group columns by start date
    by_start = defaultdict(list)
    for info in col_info:
        start_key = format_date(info['first']) if info['first'] is not None else 'No data'
        by_start[start_key].append(info)

    # Display grouped by start date
    print(f"\n    Column availability:")
    for start_date in sorted(by_start.keys()):
        cols = by_start[start_date]
        if start_date == 'No data':
            col_names = [c['col'] for c in cols]
            print(f"      No data: {', '.join(col_names)}")
        else:
            # Group by end date within start date
            by_end = defaultdict(list)
            for c in cols:
                end_key = format_date(c['last'])
                by_end[end_key].append(c)

            for end_date in sorted(by_end.keys()):
                end_cols = by_end[end_date]
                col_names = [c['col'] for c in end_cols]
                n_obs = end_cols[0]['count']
                if len(col_names) <= 4:
                    print(f"      {start_date} to {end_date} ({n_obs:,} obs): {', '.join(col_names)}")
                else:
                    print(f"      {start_date} to {end_date} ({n_obs:,} obs): {len(col_names)} columns")
                    # Show column names on next line if many
                    print(f"        {', '.join(col_names)}")


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
    for freq in ['monthly', 'quarterly']:
        summarize_file(PROCESSED_DIR / f'{freq}_curve.parquet')

    # Processed data - Mortgage Rates
    print("\n\nPROCESSED DATA - Mortgage Rates:")
    for freq in ['weekly', 'monthly', 'quarterly', 'quarterly_avg']:
        summarize_file(PROCESSED_DIR / f'{freq}_mtgrates.parquet')

    print("\n" + "=" * 70)
    print("SUMMARY COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
