"""
Process raw FRED data: rename columns, calculate forward rates, interpolate maturities,
and save to multiple frequency formats.
"""

from pathlib import Path
import numpy as np
import pandas as pd

# Directory paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
RAW_DIR = DATA_DIR / 'raw'
PROCESSED_DIR = DATA_DIR / 'processed'

# Create directories if they don't exist
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def load_raw_data():
    """Load raw FRED data."""
    input_path = RAW_DIR / 'fred_data.parquet'
    if not input_path.exists():
        raise FileNotFoundError(f"Raw data not found at {input_path}. Run 01_download.py first.")

    df = pd.read_parquet(input_path)
    df['date'] = pd.to_datetime(df['date'])
    return df


def rename_columns(df):
    """Rename FRED series to standardized names."""
    # Spread and yield mapping
    rename_map = {
        'BAMLC0A1CAAA': 's_aaa',
        'BAMLC0A1CAAAEY': 'yaaa',
        'BAMLC0A2CAA': 's_aa',
        'BAMLC0A2CAAEY': 'yaa',
        'BAMLC0A3CA': 's_a',
        'BAMLC0A3CAEY': 'ya',
        'BAMLC0A4CBBB': 's_bbb',
        'BAMLC0A4CBBBEY': 'ybbb',
        'BAMLH0A1HYBB': 's_bb',
        'BAMLH0A1HYBBEY': 'ybb',
        'BAMLH0A2HYB': 's_b',
        'BAMLH0A2HYBEY': 'yb',
        'MORTGAGE30US': 'y30m',
        'MORTGAGE15US': 'y15m',
        'OBMMIJUMBO30YF': 'y30m_jumbo',
    }

    # HQM zero-coupon yields
    hqm_map = {
        'HQMCB6MT': 'yhqz6m',
        'HQMCB1YR': 'yhqz1',
        'HQMCB2YR': 'yhqz2',
        'HQMCB3YR': 'yhqz3',
        'HQMCB5YR': 'yhqz5',
        'HQMCB10YR': 'yhqz10',
        'HQMCB15YR': 'yhqz15',
        'HQMCB20YR': 'yhqz20',
        'HQMCB30YR': 'yhqz30',
    }

    # HQM par yields
    hqm_par_map = {
        'HQMCB2YRP': 'yhqp2',
        'HQMCB5YRP': 'yhqp5',
        'HQMCB10YRP': 'yhqp10',
        'HQMCB30YRP': 'yhqp30',
    }

    all_renames = {**rename_map, **hqm_map, **hqm_par_map}
    df = df.rename(columns=all_renames)

    return df


def convert_to_decimals(df):
    """Convert percentage values to decimals."""
    # Corporate yields and spreads (reported as percentages)
    for var in ['aaa', 'aa', 'a', 'bbb', 'bb', 'b']:
        if f'y{var}' in df.columns:
            df[f'y{var}'] = df[f'y{var}'] / 100
        if f's_{var}' in df.columns:
            df[f's_{var}'] = df[f's_{var}'] / 100

    # HQM yields (reported as percentages)
    for col in df.columns:
        if col.startswith('yhqz') or col.startswith('yhqp'):
            df[col] = df[col] / 100

    # Mortgage rates (reported as percentages)
    for col in ['y30m', 'y15m', 'y30m_jumbo']:
        if col in df.columns:
            df[col] = df[col] / 100

    return df


def add_date_columns(df):
    """Add period columns for aggregation."""
    df['daten'] = df['date']
    df['datem'] = df['date'].dt.to_period('M').astype(str)
    df['dateq'] = df['date'].dt.to_period('Q').astype(str)
    return df


def create_derived_yields(df):
    """Create BB-B average and other derived variables."""
    # BB-B average
    if 'ybb' in df.columns and 'yb' in df.columns:
        df['ybb_b'] = (df['ybb'] + df['yb']) / 2
    if 's_bb' in df.columns and 's_b' in df.columns:
        df['s_bb_b'] = (df['s_bb'] + df['s_b']) / 2

    return df


def forward_fill_yields(df):
    """Forward fill missing values for yields."""
    df = df.sort_values('date').reset_index(drop=True)

    # Corporate yields (post-1996 only)
    for var in ['yaaa', 'yaa', 'ya', 'ybbb', 'ybb', 'yb', 'ybb_b']:
        if var in df.columns:
            for lag in range(1, 8):
                post_1996 = df['date'].dt.year > 1996
                null_mask = df[var].isna() & post_1996
                df.loc[null_mask, var] = df[var].shift(lag)[null_mask]

    # Mortgage rates
    for var in ['y30m', 'y15m', 'y30m_jumbo']:
        if var in df.columns:
            for lag in range(1, 8):
                null_mask = df[var].isna()
                df.loc[null_mask, var] = df[var].shift(lag)[null_mask]

    return df


def calculate_hqz_forward_rates(df):
    """Calculate HQ zero-coupon forward rates."""
    if 'yhqz6m' not in df.columns or 'yhqz1' not in df.columns:
        return df

    # Interpolated 9-month rate
    df['fhqz6m_1'] = (1 + df['yhqz1'])**2 / (1 + df['yhqz6m']) - 1
    df['yhqz9m'] = ((1 + df['fhqz6m_1'])**0.25 * (1 + df['yhqz6m'])**0.5)**(4/3) - 1

    # Forward rates
    df['fhqz1'] = df['yhqz1']
    df['fhqz2'] = (1 + df['yhqz2'])**2 / (1 + df['yhqz1']) - 1
    df['fhqz3'] = (1 + df['yhqz3'])**3 / (1 + df['yhqz2'])**2 - 1
    df['fhqz4_5'] = ((1 + df['yhqz5'])**5 / (1 + df['yhqz3'])**3)**(1/2) - 1

    # Interpolated 4-year forward
    df['fhqz4'] = (df['fhqz4_5'] - df['fhqz3']) / 2 + df['fhqz3']
    df['fhqz5'] = (1 + df['fhqz4_5'])**2 / (1 + df['fhqz4']) - 1

    # Longer-term forwards
    df['fhqz5_10'] = ((1 + df['yhqz10'])**10 / (1 + df['yhqz5'])**5)**(1/5) - 1
    df['fhqz10_15'] = ((1 + df['yhqz15'])**15 / (1 + df['yhqz10'])**10)**(1/5) - 1
    df['fhqz15_20'] = ((1 + df['yhqz20'])**20 / (1 + df['yhqz15'])**15)**(1/5) - 1
    df['fhqz20_30'] = ((1 + df['yhqz30'])**30 / (1 + df['yhqz20'])**20)**(1/10) - 1

    print("Calculated HQ zero-coupon forward rates")
    return df


def calculate_hqp_forward_rates(df):
    """Calculate HQ par forward rates and interpolated maturities."""
    if 'yhqp2' not in df.columns or 'yhqp5' not in df.columns:
        return df

    # Forward rates
    df['fhqp2_5'] = ((1 + df['yhqp5'])**5 / (1 + df['yhqp2'])**2)**(1/3) - 1
    df['fhqp5_10'] = ((1 + df['yhqp10'])**10 / (1 + df['yhqp5'])**5)**(1/5) - 1
    df['fhqp10_30'] = ((1 + df['yhqp30'])**30 / (1 + df['yhqp10'])**10)**(1/20) - 1

    # Copy short-term from zero-coupon
    df['yhqp6m'] = df.get('yhqz6m', np.nan)
    df['yhqp9m'] = df.get('yhqz9m', np.nan)
    df['yhqp1'] = df.get('yhqz1', np.nan)

    # Interpolated maturities
    df['fhqp2'] = ((1 + df['yhqp2'])**2 / (1 + df['yhqp1']))**(1) - 1
    df['yhqp3'] = ((1 + df['yhqp2'])**2 * (1 + df['fhqp2_5']))**(1/3) - 1
    df['yhqp15'] = ((1 + df['yhqp10'])**10 * (1 + df['fhqp10_30'])**5)**(1/15) - 1
    df['yhqp20'] = ((1 + df['yhqp10'])**10 * (1 + df['fhqp10_30'])**10)**(1/20) - 1
    df['yhqp4'] = ((1 + df['yhqp3'])**3 * (1 + df['fhqp2_5'])**1)**(1/4) - 1
    df['yhqp6'] = ((1 + df['yhqp5'])**5 * (1 + df['fhqp5_10'])**1)**(1/6) - 1

    print("Calculated HQ par forward rates and interpolated maturities")
    return df


def save_rating_data(df):
    """Save corporate credit ratings data at multiple frequencies."""
    print("\nSaving corporate credit rating data...")

    # Select relevant columns
    rating_cols = ['daten', 'datem', 'dateq']
    yield_cols = [c for c in df.columns if c.startswith(('y', 's_')) and not c.startswith('yhq')]
    rating_cols.extend([c for c in yield_cols if c in df.columns])

    df_rating = df[rating_cols].copy()

    # Daily
    df_rating.to_parquet(PROCESSED_DIR / 'daily_rating.parquet')
    print(f"  Saved daily_rating.parquet: {len(df_rating)} rows")

    # End of month
    df_rating['eom'] = df_rating.groupby('datem')['daten'].transform('max')
    df_monthly = df_rating[df_rating['daten'] == df_rating['eom']].drop(columns=['eom'])
    df_monthly.to_parquet(PROCESSED_DIR / 'monthly_rating.parquet')
    print(f"  Saved monthly_rating.parquet: {len(df_monthly)} rows")

    # End of quarter
    df_rating['eoq'] = df_rating.groupby('dateq')['daten'].transform('max')
    df_quarterly = df_rating[df_rating['daten'] == df_rating['eoq']].drop(columns=['eoq'])
    df_quarterly.to_parquet(PROCESSED_DIR / 'quarterly_rating.parquet')
    print(f"  Saved quarterly_rating.parquet: {len(df_quarterly)} rows")

    # Quarterly average
    numeric_cols = df_rating.select_dtypes(include=[np.number]).columns.tolist()
    df_qavg = df_rating.groupby('dateq')[numeric_cols].mean().reset_index()
    df_qavg.to_parquet(PROCESSED_DIR / 'quarterly_avg_rating.parquet')
    print(f"  Saved quarterly_avg_rating.parquet: {len(df_qavg)} rows")


def save_curve_data(df):
    """Save HQM curve data at multiple frequencies."""
    print("\nSaving HQM curve data...")

    # Select relevant columns
    curve_cols = ['daten', 'datem', 'dateq']
    hq_cols = [c for c in df.columns if c.startswith(('yhqz', 'yhqp', 'fhqz', 'fhqp'))]
    curve_cols.extend(hq_cols)

    df_curve = df[curve_cols].copy()

    # End of month (curve_end)
    df_curve['eom'] = df_curve.groupby('datem')['daten'].transform('max')
    df_monthly = df_curve[df_curve['daten'] == df_curve['eom']].drop(columns=['eom'])
    df_monthly.to_parquet(PROCESSED_DIR / 'monthly_curve_end.parquet')
    print(f"  Saved monthly_curve_end.parquet: {len(df_monthly)} rows")

    # End of quarter
    df_curve['eoq'] = df_curve.groupby('dateq')['daten'].transform('max')
    df_quarterly = df_curve[df_curve['daten'] == df_curve['eoq']].drop(columns=['eoq'])
    df_quarterly.to_parquet(PROCESSED_DIR / 'quarterly_curve_end.parquet')
    print(f"  Saved quarterly_curve_end.parquet: {len(df_quarterly)} rows")

    # Monthly average (curve_avg)
    numeric_cols = df_curve.select_dtypes(include=[np.number]).columns.tolist()
    df_mavg = df_curve.groupby('datem')[numeric_cols].mean().reset_index()
    df_mavg.to_parquet(PROCESSED_DIR / 'monthly_curve_avg.parquet')
    print(f"  Saved monthly_curve_avg.parquet: {len(df_mavg)} rows")

    # Quarterly average
    df_qavg = df_curve.groupby('dateq')[numeric_cols].mean().reset_index()
    df_qavg.to_parquet(PROCESSED_DIR / 'quarterly_curve_avg.parquet')
    print(f"  Saved quarterly_curve_avg.parquet: {len(df_qavg)} rows")


def save_mortgage_data(df):
    """Save mortgage rate data at multiple frequencies."""
    print("\nSaving mortgage rate data...")

    # Select relevant columns
    mtg_cols = ['daten', 'datem', 'dateq']
    mtg_rate_cols = [c for c in ['y30m', 'y15m', 'y30m_jumbo'] if c in df.columns]
    mtg_cols.extend(mtg_rate_cols)

    if len(mtg_rate_cols) == 0:
        print("  No mortgage rate data found, skipping...")
        return

    df_mtg = df[mtg_cols].copy()

    # Weekly (mortgage data is weekly)
    df_mtg.to_parquet(PROCESSED_DIR / 'weekly_mtgrates.parquet')
    print(f"  Saved weekly_mtgrates.parquet: {len(df_mtg)} rows")

    # End of month
    df_mtg['eom'] = df_mtg.groupby('datem')['daten'].transform('max')
    df_monthly = df_mtg[df_mtg['daten'] == df_mtg['eom']].drop(columns=['eom'])
    df_monthly.to_parquet(PROCESSED_DIR / 'monthly_mtgrates.parquet')
    print(f"  Saved monthly_mtgrates.parquet: {len(df_monthly)} rows")

    # End of quarter
    df_mtg['eoq'] = df_mtg.groupby('dateq')['daten'].transform('max')
    df_quarterly = df_mtg[df_mtg['daten'] == df_mtg['eoq']].drop(columns=['eoq'])
    df_quarterly.to_parquet(PROCESSED_DIR / 'quarterly_mtgrates.parquet')
    print(f"  Saved quarterly_mtgrates.parquet: {len(df_quarterly)} rows")

    # Quarterly average
    numeric_cols = df_mtg.select_dtypes(include=[np.number]).columns.tolist()
    df_qavg = df_mtg.groupby('dateq')[numeric_cols].mean().reset_index()
    df_qavg.to_parquet(PROCESSED_DIR / 'quarterly_avg_mtgrates.parquet')
    print(f"  Saved quarterly_avg_mtgrates.parquet: {len(df_qavg)} rows")


def main():
    """Run all processing tasks."""
    print("=" * 70)
    print("PROCESSING RAW DATA")
    print("=" * 70)

    # Load data
    print("\nLoading raw data...")
    df = load_raw_data()
    print(f"Loaded {len(df)} rows")

    # Process data
    df = rename_columns(df)
    df = convert_to_decimals(df)
    df = add_date_columns(df)
    df = create_derived_yields(df)
    df = forward_fill_yields(df)
    df = calculate_hqz_forward_rates(df)
    df = calculate_hqp_forward_rates(df)

    # Save at different frequencies
    save_rating_data(df)
    save_curve_data(df)
    save_mortgage_data(df)

    print("\n" + "=" * 70)
    print("PROCESSING COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
