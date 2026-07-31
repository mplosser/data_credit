"""
Process raw FRED data: rename variables, calculate forward rates,
interpolate maturities, and save to multiple frequency formats with metadata.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Directory paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
RAW_DIR = DATA_DIR / 'raw'
PROCESSED_DIR = DATA_DIR / 'processed'

# Create directories if they don't exist
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Variable definitions: FRED ID -> (variable name, description)
VARIABLE_DEFINITIONS = {
    # Corporate yields
    'BAMLC0A1CAAAEY': ('y_aaa', 'ICE BofA AAA US Corporate Index Effective Yield'),
    'BAMLC0A2CAAEY': ('y_aa', 'ICE BofA AA US Corporate Index Effective Yield'),
    'BAMLC0A3CAEY': ('y_a', 'ICE BofA A US Corporate Index Effective Yield'),
    'BAMLC0A4CBBBEY': ('y_bbb', 'ICE BofA BBB US Corporate Index Effective Yield'),
    'BAMLH0A1HYBBEY': ('y_bb', 'ICE BofA BB US High Yield Index Effective Yield'),
    'BAMLH0A2HYBEY': ('y_b', 'ICE BofA B US High Yield Index Effective Yield'),
    # Corporate spreads
    'BAMLC0A1CAAA': ('s_aaa', 'ICE BofA AAA US Corporate Index Option-Adjusted Spread'),
    'BAMLC0A2CAA': ('s_aa', 'ICE BofA AA US Corporate Index Option-Adjusted Spread'),
    'BAMLC0A3CA': ('s_a', 'ICE BofA A US Corporate Index Option-Adjusted Spread'),
    'BAMLC0A4CBBB': ('s_bbb', 'ICE BofA BBB US Corporate Index Option-Adjusted Spread'),
    'BAMLH0A1HYBB': ('s_bb', 'ICE BofA BB US High Yield Index Option-Adjusted Spread'),
    'BAMLH0A2HYB': ('s_b', 'ICE BofA B US High Yield Index Option-Adjusted Spread'),
    # Mortgage rates
    'MORTGAGE30US': ('ym_30', '30-Year Fixed Rate Mortgage Average'),
    'MORTGAGE15US': ('ym_15', '15-Year Fixed Rate Mortgage Average'),
    'OBMMIJUMBO30YF': ('ym_30_jumbo', '30-Year Jumbo Mortgage Rate'),
    # HQM zero-coupon yields
    'HQMCB6MT': ('hqm_zero_6m', 'HQM Corporate Bond Zero-Coupon Yield 6-Month'),
    'HQMCB1YR': ('hqm_zero_1y', 'HQM Corporate Bond Zero-Coupon Yield 1-Year'),
    'HQMCB2YR': ('hqm_zero_2y', 'HQM Corporate Bond Zero-Coupon Yield 2-Year'),
    'HQMCB3YR': ('hqm_zero_3y', 'HQM Corporate Bond Zero-Coupon Yield 3-Year'),
    'HQMCB5YR': ('hqm_zero_5y', 'HQM Corporate Bond Zero-Coupon Yield 5-Year'),
    'HQMCB10YR': ('hqm_zero_10y', 'HQM Corporate Bond Zero-Coupon Yield 10-Year'),
    'HQMCB15YR': ('hqm_zero_15y', 'HQM Corporate Bond Zero-Coupon Yield 15-Year'),
    'HQMCB20YR': ('hqm_zero_20y', 'HQM Corporate Bond Zero-Coupon Yield 20-Year'),
    'HQMCB30YR': ('hqm_zero_30y', 'HQM Corporate Bond Zero-Coupon Yield 30-Year'),
    # HQM par yields
    'HQMCB2YRP': ('hqm_par_2y', 'HQM Corporate Bond Par Yield 2-Year'),
    'HQMCB5YRP': ('hqm_par_5y', 'HQM Corporate Bond Par Yield 5-Year'),
    'HQMCB10YRP': ('hqm_par_10y', 'HQM Corporate Bond Par Yield 10-Year'),
    'HQMCB30YRP': ('hqm_par_30y', 'HQM Corporate Bond Par Yield 30-Year'),
}

# Descriptions for derived variables
DERIVED_DESCRIPTIONS = {
    'y_bb_b': 'Average of BB and B Corporate Yields',
    's_bb_b': 'Average of BB and B Corporate Spreads',
    'hqm_zero_9m': 'HQM Corporate Bond Zero-Coupon Yield 9-Month (interpolated)',
    'hqm_par_6m': 'HQM Corporate Bond Par Yield 6-Month (from zero-coupon)',
    'hqm_par_9m': 'HQM Corporate Bond Par Yield 9-Month (from zero-coupon)',
    'hqm_par_1y': 'HQM Corporate Bond Par Yield 1-Year (from zero-coupon)',
    'hqm_par_3y': 'HQM Corporate Bond Par Yield 3-Year (interpolated)',
    'hqm_par_4y': 'HQM Corporate Bond Par Yield 4-Year (interpolated)',
    'hqm_par_6y': 'HQM Corporate Bond Par Yield 6-Year (interpolated)',
    'hqm_par_15y': 'HQM Corporate Bond Par Yield 15-Year (interpolated)',
    'hqm_par_20y': 'HQM Corporate Bond Par Yield 20-Year (interpolated)',
    'fwd_zero_6m_1y': 'HQM Zero-Coupon Forward Rate 6M-1Y',
    'fwd_zero_1y': 'HQM Zero-Coupon Forward Rate 1Y',
    'fwd_zero_2y': 'HQM Zero-Coupon Forward Rate 2Y',
    'fwd_zero_3y': 'HQM Zero-Coupon Forward Rate 3Y',
    'fwd_zero_4y': 'HQM Zero-Coupon Forward Rate 4Y (interpolated)',
    'fwd_zero_4y_5y': 'HQM Zero-Coupon Forward Rate 4Y-5Y',
    'fwd_zero_5y': 'HQM Zero-Coupon Forward Rate 5Y',
    'fwd_zero_5y_10y': 'HQM Zero-Coupon Forward Rate 5Y-10Y',
    'fwd_zero_10y_15y': 'HQM Zero-Coupon Forward Rate 10Y-15Y',
    'fwd_zero_15y_20y': 'HQM Zero-Coupon Forward Rate 15Y-20Y',
    'fwd_zero_20y_30y': 'HQM Zero-Coupon Forward Rate 20Y-30Y',
    'fwd_par_2y': 'HQM Par Forward Rate 2Y',
    'fwd_par_2y_5y': 'HQM Par Forward Rate 2Y-5Y',
    'fwd_par_5y_10y': 'HQM Par Forward Rate 5Y-10Y',
    'fwd_par_10y_30y': 'HQM Par Forward Rate 10Y-30Y',
}


def get_rename_map():
    """Get FRED ID to variable name mapping."""
    return {fred_id: var_name for fred_id, (var_name, _) in VARIABLE_DEFINITIONS.items()}


def get_description_map():
    """Get variable name to description mapping."""
    desc_map = {var_name: desc for _, (var_name, desc) in VARIABLE_DEFINITIONS.items()}
    desc_map.update(DERIVED_DESCRIPTIONS)
    return desc_map


def load_raw_data():
    """Load raw FRED data."""
    input_path = RAW_DIR / 'fred_data.parquet'
    if not input_path.exists():
        raise FileNotFoundError(f"Raw data not found at {input_path}. Run 01_download.py first.")

    df = pd.read_parquet(input_path)
    df['date'] = pd.to_datetime(df['date'])
    return df


def rename_variables(df):
    """Rename FRED series IDs to meaningful names."""
    rename_map = get_rename_map()
    df = df.rename(columns=rename_map)
    return df


def convert_to_decimals(df):
    """Convert percentage values to decimals."""
    for col in df.columns:
        if col not in ['date', 'daten', 'datem', 'dateq'] and df[col].dtype in ['float64', 'int64']:
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
    if 'y_bb' in df.columns and 'y_b' in df.columns:
        df['y_bb_b'] = (df['y_bb'] + df['y_b']) / 2
    if 's_bb' in df.columns and 's_b' in df.columns:
        df['s_bb_b'] = (df['s_bb'] + df['s_b']) / 2
    return df


def forward_fill_yields(df):
    """Forward fill missing values for yields."""
    df = df.sort_values('date').reset_index(drop=True)

    # Corporate yields and spreads (post-1996 only)
    corp_cols = [c for c in df.columns if c.startswith('y_') or c.startswith('s_')]
    for var in corp_cols:
        for lag in range(1, 8):
            post_1996 = df['date'].dt.year > 1996
            null_mask = df[var].isna() & post_1996
            df.loc[null_mask, var] = df[var].shift(lag)[null_mask]

    # Mortgage rates
    mtg_cols = [c for c in df.columns if c.startswith('ym_')]
    for var in mtg_cols:
        for lag in range(1, 8):
            null_mask = df[var].isna()
            df.loc[null_mask, var] = df[var].shift(lag)[null_mask]

    return df


def calculate_hqz_forward_rates(df):
    """Calculate HQ zero-coupon forward rates."""
    if 'hqm_zero_6m' not in df.columns or 'hqm_zero_1y' not in df.columns:
        return df

    # Interpolated 9-month rate
    df['fwd_zero_6m_1y'] = (1 + df['hqm_zero_1y'])**2 / (1 + df['hqm_zero_6m']) - 1
    df['hqm_zero_9m'] = ((1 + df['fwd_zero_6m_1y'])**0.25 * (1 + df['hqm_zero_6m'])**0.5)**(4/3) - 1

    # Forward rates
    df['fwd_zero_1y'] = df['hqm_zero_1y']
    df['fwd_zero_2y'] = (1 + df['hqm_zero_2y'])**2 / (1 + df['hqm_zero_1y']) - 1
    df['fwd_zero_3y'] = (1 + df['hqm_zero_3y'])**3 / (1 + df['hqm_zero_2y'])**2 - 1
    df['fwd_zero_4y_5y'] = ((1 + df['hqm_zero_5y'])**5 / (1 + df['hqm_zero_3y'])**3)**(1/2) - 1

    # Interpolated 4-year forward
    df['fwd_zero_4y'] = (df['fwd_zero_4y_5y'] - df['fwd_zero_3y']) / 2 + df['fwd_zero_3y']
    df['fwd_zero_5y'] = (1 + df['fwd_zero_4y_5y'])**2 / (1 + df['fwd_zero_4y']) - 1

    # Longer-term forwards
    df['fwd_zero_5y_10y'] = ((1 + df['hqm_zero_10y'])**10 / (1 + df['hqm_zero_5y'])**5)**(1/5) - 1
    df['fwd_zero_10y_15y'] = ((1 + df['hqm_zero_15y'])**15 / (1 + df['hqm_zero_10y'])**10)**(1/5) - 1
    df['fwd_zero_15y_20y'] = ((1 + df['hqm_zero_20y'])**20 / (1 + df['hqm_zero_15y'])**15)**(1/5) - 1
    df['fwd_zero_20y_30y'] = ((1 + df['hqm_zero_30y'])**30 / (1 + df['hqm_zero_20y'])**20)**(1/10) - 1

    print("Calculated HQ zero-coupon forward rates")
    return df


def calculate_hqp_forward_rates(df):
    """Calculate HQ par forward rates and interpolated maturities."""
    if 'hqm_par_2y' not in df.columns or 'hqm_par_5y' not in df.columns:
        return df

    # Forward rates
    df['fwd_par_2y_5y'] = ((1 + df['hqm_par_5y'])**5 / (1 + df['hqm_par_2y'])**2)**(1/3) - 1
    df['fwd_par_5y_10y'] = ((1 + df['hqm_par_10y'])**10 / (1 + df['hqm_par_5y'])**5)**(1/5) - 1
    df['fwd_par_10y_30y'] = ((1 + df['hqm_par_30y'])**30 / (1 + df['hqm_par_10y'])**10)**(1/20) - 1

    # Copy short-term from zero-coupon
    df['hqm_par_6m'] = df.get('hqm_zero_6m', np.nan)
    df['hqm_par_9m'] = df.get('hqm_zero_9m', np.nan)
    df['hqm_par_1y'] = df.get('hqm_zero_1y', np.nan)

    # Interpolated maturities
    df['fwd_par_2y'] = ((1 + df['hqm_par_2y'])**2 / (1 + df['hqm_par_1y']))**(1) - 1
    df['hqm_par_3y'] = ((1 + df['hqm_par_2y'])**2 * (1 + df['fwd_par_2y_5y']))**(1/3) - 1
    df['hqm_par_15y'] = ((1 + df['hqm_par_10y'])**10 * (1 + df['fwd_par_10y_30y'])**5)**(1/15) - 1
    df['hqm_par_20y'] = ((1 + df['hqm_par_10y'])**10 * (1 + df['fwd_par_10y_30y'])**10)**(1/20) - 1
    df['hqm_par_4y'] = ((1 + df['hqm_par_3y'])**3 * (1 + df['fwd_par_2y_5y'])**1)**(1/4) - 1
    df['hqm_par_6y'] = ((1 + df['hqm_par_5y'])**5 * (1 + df['fwd_par_5y_10y'])**1)**(1/6) - 1

    print("Calculated HQ par forward rates and interpolated maturities")
    return df


def save_with_metadata(df, filepath, description_map):
    """Save DataFrame to parquet with column descriptions as metadata."""
    column_metadata = {col: description_map.get(col, '') for col in df.columns if col in description_map}

    table = pa.Table.from_pandas(df)

    new_metadata = {
        b'column_descriptions': str(column_metadata).encode(),
        b'source': b'FRED API - Federal Reserve Economic Data',
    }
    new_schema = table.schema.with_metadata(new_metadata)
    table = table.cast(new_schema)

    pq.write_table(table, filepath)


def save_rating_data(df, description_map):
    """Save corporate credit ratings data at multiple frequencies."""
    print("\nSaving corporate credit rating data...")

    rating_cols = ['daten', 'datem', 'dateq']
    yield_cols = [c for c in df.columns if c.startswith(('y_', 's_'))]
    rating_cols.extend([c for c in yield_cols if c in df.columns])

    df_rating = df[rating_cols].copy()

    # Drop rows where all data columns are null
    df_rating = df_rating.dropna(subset=yield_cols, how='all')

    # Daily
    save_with_metadata(df_rating, PROCESSED_DIR / 'daily_rating.parquet', description_map)
    print(f"  Saved daily_rating.parquet: {len(df_rating)} rows")

    # End of month
    df_rating['eom'] = df_rating.groupby('datem')['daten'].transform('max')
    df_monthly = df_rating[df_rating['daten'] == df_rating['eom']].drop(columns=['eom'])
    save_with_metadata(df_monthly, PROCESSED_DIR / 'monthly_rating.parquet', description_map)
    print(f"  Saved monthly_rating.parquet: {len(df_monthly)} rows")

    # End of quarter
    df_rating['eoq'] = df_rating.groupby('dateq')['daten'].transform('max')
    df_quarterly = df_rating[df_rating['daten'] == df_rating['eoq']].drop(columns=['eoq'])
    save_with_metadata(df_quarterly, PROCESSED_DIR / 'quarterly_rating.parquet', description_map)
    print(f"  Saved quarterly_rating.parquet: {len(df_quarterly)} rows")

    # Quarterly average
    numeric_cols = df_rating.select_dtypes(include=[np.number]).columns.tolist()
    df_qavg = df_rating.groupby('dateq')[numeric_cols].mean().reset_index()
    save_with_metadata(df_qavg, PROCESSED_DIR / 'quarterly_avg_rating.parquet', description_map)
    print(f"  Saved quarterly_avg_rating.parquet: {len(df_qavg)} rows")


def save_curve_data(df, description_map):
    """Save HQM curve data (already monthly averaged from FRED)."""
    print("\nSaving HQM curve data...")

    curve_cols = ['datem', 'dateq']
    hq_cols = [c for c in df.columns if c.startswith(('hqm_', 'fwd_'))]
    curve_cols.extend(hq_cols)

    df_curve = df[curve_cols].copy()
    numeric_cols = [c for c in hq_cols if c in df_curve.columns]

    # Drop rows where all data columns are null
    df_curve = df_curve.dropna(subset=numeric_cols, how='all')

    # Monthly average (FRED HQM data is already monthly averaged)
    df_monthly = df_curve.groupby('datem')[numeric_cols].mean().reset_index()
    save_with_metadata(df_monthly, PROCESSED_DIR / 'monthly_curve.parquet', description_map)
    print(f"  Saved monthly_curve.parquet: {len(df_monthly)} rows")

    # Quarterly average (from monthly averages)
    df_curve['dateq'] = df_curve['datem'].str[:4] + 'Q' + ((pd.to_datetime(df_curve['datem']).dt.month - 1) // 3 + 1).astype(str)
    df_quarterly = df_curve.groupby('dateq')[numeric_cols].mean().reset_index()
    save_with_metadata(df_quarterly, PROCESSED_DIR / 'quarterly_curve.parquet', description_map)
    print(f"  Saved quarterly_curve.parquet: {len(df_quarterly)} rows")

    # Quarterly END-OF-QUARTER (spot): last month present in each quarter.
    # HQM monthly values are end-of-month spot rates, so the quarter's final
    # month (Mar/Jun/Sep/Dec) IS the EOQ spot rate -- directly comparable to
    # end-of-quarter Treasury yields. Use this curve for VALUATION (duration /
    # fair-value spreads, where the impact is on value at a specific date); use
    # the quarterly *average* above for FLOW analysis (deposit betas, income,
    # estimated over the course of a quarter). Netting an averaged corporate
    # yield against a spot Treasury produced spurious negative spreads in fast
    # intra-quarter rate moves (e.g. 2022Q1/Q3).
    df_end = df_curve.sort_values('datem').groupby('dateq')[numeric_cols].last().reset_index()
    save_with_metadata(df_end, PROCESSED_DIR / 'quarterly_curve_end.parquet', description_map)
    print(f"  Saved quarterly_curve_end.parquet: {len(df_end)} rows")


def save_mortgage_data(df, description_map):
    """Save mortgage rate data at multiple frequencies."""
    print("\nSaving mortgage rate data...")

    mtg_cols = ['daten', 'datem', 'dateq']
    mtg_rate_cols = [c for c in df.columns if c.startswith('ym_')]
    mtg_cols.extend(mtg_rate_cols)

    if len(mtg_rate_cols) == 0:
        print("  No mortgage rate data found, skipping...")
        return

    df_mtg = df[mtg_cols].copy()

    # Drop rows where all data columns are null
    df_mtg = df_mtg.dropna(subset=mtg_rate_cols, how='all')

    # Weekly (mortgage data is weekly)
    save_with_metadata(df_mtg, PROCESSED_DIR / 'weekly_mtgrates.parquet', description_map)
    print(f"  Saved weekly_mtgrates.parquet: {len(df_mtg)} rows")

    # End of month
    df_mtg['eom'] = df_mtg.groupby('datem')['daten'].transform('max')
    df_monthly = df_mtg[df_mtg['daten'] == df_mtg['eom']].drop(columns=['eom'])
    save_with_metadata(df_monthly, PROCESSED_DIR / 'monthly_mtgrates.parquet', description_map)
    print(f"  Saved monthly_mtgrates.parquet: {len(df_monthly)} rows")

    # End of quarter
    df_mtg['eoq'] = df_mtg.groupby('dateq')['daten'].transform('max')
    df_quarterly = df_mtg[df_mtg['daten'] == df_mtg['eoq']].drop(columns=['eoq'])
    save_with_metadata(df_quarterly, PROCESSED_DIR / 'quarterly_mtgrates.parquet', description_map)
    print(f"  Saved quarterly_mtgrates.parquet: {len(df_quarterly)} rows")

    # Quarterly average
    numeric_cols = df_mtg.select_dtypes(include=[np.number]).columns.tolist()
    df_qavg = df_mtg.groupby('dateq')[numeric_cols].mean().reset_index()
    save_with_metadata(df_qavg, PROCESSED_DIR / 'quarterly_avg_mtgrates.parquet', description_map)
    print(f"  Saved quarterly_avg_mtgrates.parquet: {len(df_qavg)} rows")


def main():
    """Run all processing tasks."""
    print("=" * 70)
    print("PROCESSING RAW DATA")
    print("=" * 70)

    description_map = get_description_map()
    print(f"\nLoaded {len(VARIABLE_DEFINITIONS)} variable definitions")

    # Load data
    print("\nLoading raw data...")
    df = load_raw_data()
    print(f"Loaded {len(df)} rows")

    # Process data
    df = rename_variables(df)
    df = convert_to_decimals(df)
    df = add_date_columns(df)
    df = create_derived_yields(df)
    df = forward_fill_yields(df)
    df = calculate_hqz_forward_rates(df)
    df = calculate_hqp_forward_rates(df)

    # Save at different frequencies
    save_rating_data(df, description_map)
    save_curve_data(df, description_map)
    save_mortgage_data(df, description_map)

    print("\n" + "=" * 70)
    print("PROCESSING COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
