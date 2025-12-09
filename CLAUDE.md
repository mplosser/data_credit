# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Downloads corporate credit yields, spreads and the HQM corporate credit curve from FRED, processes it into standardized formats with forward rates and interpolated maturities, and saves as Parquet files at multiple frequencies (daily, monthly, quarterly, quarterly average).

## Commands

```bash
# Full pipeline
python 01_download.py    # Download from FRED and NY Fed
python 02_parse.py       # Process and calculate forward rates
python 03_summarize.py   # Summarize output files

# Setup
pip install -r requirements.txt
cp .env.example .env     # Then add FRED API key
```

## Data Sources

**FRED Corporate Credit by Rating:** Corporate Yields and Option-Adjsuted Spreads from ICE BofA US Indices: AAA, AA A, BBB, BB, B, and High Yield (St. Louis Fred API)
**UST High Quality Corporate Credit Curve End of Month** HQM Corporate Credit Curve Par Yields (https://home.treasury.gov/data/treasury-coupon-issues-and-corporate-bond-yield-curve/corporate-bond-yield-curve)
**UST High Quality Corporate Credit Curve Monthly Average** HQM Corporate Credit Curve Par Yields (https://home.treasury.gov/data/treasury-coupon-issues-and-corporate-bond-yield-curve/corporate-bond-yield-curve)
**FRED Mortgage Rates:** MORTGAGE30US OBMMIJUMBO30YF MORTGAGE15US  (St. Louis Fred API)

## Output Files

Corporate Credit yields and spreads:  saved at daily, end of month, end of quarter, and quarterly average. (4 files)
UST Corporate credit curves save at end of month and end of quarter (if the end ofg month series) and at monthly average and quarterly average if its the average series. (2 files each)
Mortgage rates saved at weekly, end of month, end of quarter and quarterly average. (4 files)

Three yield types, each saved at four frequencies:
- `daily_*.parquet` - All trading days
- `monthly_*.parquet` - End of month
- `quarterly_*.parquet` - End of quarter
- `quarterly_avg_*.parquet` - Daily averages over quarter

File prefixes: `rating`, `curve_end`, `curve_avg`, and `mtgrates`


## Key Variables

## File Structure

raw data saved to data/raw
processed parquest files to data/processed


## Example prior code


# Configuration
FRED_API_KEY = '69e0b3bca397610384c2a3cb5b0e971a'
MAX_DATE = '2025Q2'  # Update as needed

# Directory paths
BASE_DIR = Path.cwd().parent  # Assuming notebook is in notebooks/ folder
DATA_DIR = BASE_DIR / 'data'
INPUT_DIR = DATA_DIR / 'raw'
INTER_DIR = DATA_DIR / 'processed'
OUTPUT_DIR = DATA_DIR / 'output'

# Create directories if they don't exist
for directory in [DATA_DIR, INPUT_DIR, INTER_DIR, OUTPUT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

print(f"Base directory: {BASE_DIR}")
print(f"Data directory: {DATA_DIR}")
print(f"Processed directory: {INTER_DIR}")


# Initialize FRED API
fred = Fred(api_key=FRED_API_KEY)
print("FRED API initialized successfully")



print("Importing corporate spreads from FRED...\n")

spread_series = [
    'MORTGAGE30US',      # 30-Year Fixed Rate Mortgage Average
    'BAMLC0A4CBBB',      # BBB Spread
    'BAMLC0A4CBBBEY',    # BBB Effective Yield
    'BAMLC0A1CAAA',      # AAA Spread
    'BAMLC0A1CAAAEY',    # AAA Effective Yield
    'BAMLC0A3CA',        # A Spread
    'BAMLH0A2HYBEY',     # High Yield B Effective Yield
    'BAMLH0A2HYB',       # High Yield B Spread
    'BAMLC0A3CAEY',      # A Effective Yield
    'BAMLH0A1HYBB',      # High Yield BB Spread
    'BAMLH0A1HYBBEY',    # High Yield BB Effective Yield
    'BAMLC0A2CAA',       # AA Spread
    'BAMLC0A2CAAEY',     # AA Effective Yield
    # High Quality Market Corporate Bond indices
    'HQMCB6MT',  'HQMCB1YR',  'HQMCB2YR',  'HQMCB3YR',  'HQMCB5YR',
    'HQMCB10YR', 'HQMCB15YR', 'HQMCB20YR', 'HQMCB30YR',
    # Par yields
    'HQMCB30YRP', 'HQMCB10YRP', 'HQMCB5YRP', 'HQMCB2YRP'
]

# Download spread data
spread_dict = {}
for series in spread_series:
    try:
        print(f"  Downloading {series}...")
        spread_dict[series] = fred.get_series(series, observation_start='1980-01-01')
    except Exception as e:
        print(f"  Warning: Could not download {series}: {e}")

# Combine into DataFrame
df_spreads = pd.DataFrame(spread_dict)
df_spreads.index.name = 'daten'
df_spreads = df_spreads.reset_index()

print(f"\nDownloaded {len(df_spreads)} observations")
df_spreads.head()


# Create date variables
df_spreads['date'] = pd.PeriodIndex(df_spreads['daten'], freq='Q').astype(str)  # As string for Parquet
df_spreads['datem'] = pd.PeriodIndex(df_spreads['daten'], freq='M').astype(str)  # As string for Parquet

# Filter by date
df_spreads = df_spreads[(df_spreads['date'] >= '1980Q1') & (df_spreads['date'] <= str(max_date_period))]
df_spreads['eoq_date'] = df_spreads.groupby('date')['daten'].transform('max')

# Rename and transform mortgage rate
df_spreads['y30m'] = df_spreads['MORTGAGE30US'] / 100

# Rename spread variables
spread_mapping = {
    'BAMLC0A4CBBB': 's_bbb',
    'BAMLC0A4CBBBEY': 'ybbb',
    'BAMLH0A2HYB': 's_b',
    'BAMLH0A2HYBEY': 'yb',
    'BAMLC0A1CAAA': 's_aaa',
    'BAMLC0A1CAAAEY': 'yaaa',
    'BAMLC0A3CA': 's_a',
    'BAMLC0A3CAEY': 'ya',
    'BAMLH0A1HYBB': 's_bb',
    'BAMLH0A1HYBBEY': 'ybb',
    'BAMLC0A2CAA': 's_aa',
    'BAMLC0A2CAAEY': 'yaa'
}

df_spreads = df_spreads.rename(columns=spread_mapping)

# Create BB-B average
df_spreads['s_bb_b'] = (df_spreads['s_bb'] + df_spreads['s_b']) / 2
df_spreads['ybb_b'] = (df_spreads['ybb'] + df_spreads['yb']) / 2

# Convert to decimal
for var in ['a', 'aa', 'aaa', 'b', 'bb', 'bbb', 'bb_b']:
    if f'y{var}' in df_spreads.columns:
        df_spreads[f'y{var}'] = df_spreads[f'y{var}'] / 100
    if f's_{var}' in df_spreads.columns:
        df_spreads[f's_{var}'] = df_spreads[f's_{var}'] / 100

print("Renamed and transformed spread variables")
df_spreads[['daten', 'date', 'y30m', 's_aaa', 's_bbb', 'yaaa', 'ybbb']].head()


# Process HQ corporate bond rates (monthly max by month)
for var in ['6MT', '1YR', '2YR', '3YR', '5YR', '10YR', '15YR', '20YR', '30YR']:
    col = f'HQMCB{var}'
    if col in df_spreads.columns:
        maturity_name = var.replace('MT', 'm').replace('YR', '')
        df_spreads[f'yhqz{maturity_name}'] = df_spreads.groupby('datem')[col].transform('max') / 100

# Process par yields
for var in ['2YR', '5YR', '10YR', '30YR']:
    col = f'HQMCB{var}P'
    if col in df_spreads.columns:
        maturity_name = var.replace('YR', '')
        df_spreads[f'yhqp{maturity_name}'] = df_spreads.groupby('datem')[col].transform('max') / 100

print("Processed HQ corporate bond indices")
hq_cols = [col for col in df_spreads.columns if col.startswith('yhq')]
df_spreads[['daten', 'date'] + hq_cols[:5]].head()


# Sort and forward fill missing values
df_spreads = df_spreads.sort_values('daten').reset_index(drop=True)

# Forward fill corporate yields (post-1996)
for var in ['bbb', 'bb', 'b', 'aaa', 'aa', 'a', 'bb_b']:
    if f'y{var}' in df_spreads.columns:
        for lag in range(1, 8):
            post_1996 = df_spreads['daten'].dt.year > 1996
            null_mask = df_spreads[f'y{var}'].isna() & post_1996
            df_spreads.loc[null_mask, f'y{var}'] = df_spreads[f'y{var}'].shift(lag)[null_mask]

# Forward fill mortgage rate
for lag in range(1, 8):
    null_mask = df_spreads['y30m'].isna()
    df_spreads.loc[null_mask, 'y30m'] = df_spreads['y30m'].shift(lag)[null_mask]

print("Forward-filled missing values")
print(f"Missing values in ybbb: {df_spreads['ybbb'].isna().sum()}")
print(f"Missing values in y30m: {df_spreads['y30m'].isna().sum()}")


# Calculate HQ zero-coupon forward rates
if 'yhqz6m' in df_spreads.columns and 'yhqz1' in df_spreads.columns:
    df_spreads['fhqz6m_1'] = (1 + df_spreads['yhqz1'])**2 / (1 + df_spreads['yhqz6m']) - 1
    df_spreads['yhqz9m'] = ((1 + df_spreads['fhqz6m_1'])**0.25 * (1 + df_spreads['yhqz6m'])**0.5)**(4/3) - 1

    df_spreads['fhqz1'] = df_spreads['yhqz1']
    df_spreads['fhqz2'] = (1 + df_spreads['yhqz2'])**2 / (1 + df_spreads['yhqz1']) - 1
    df_spreads['fhqz3'] = (1 + df_spreads['yhqz3'])**3 / (1 + df_spreads['yhqz2'])**2 - 1
    df_spreads['fhqz4_5'] = ((1 + df_spreads['yhqz5'])**5 / (1 + df_spreads['yhqz3'])**3)**(1/2) - 1

    df_spreads['fhqz4'] = (df_spreads['fhqz4_5'] - df_spreads['fhqz3']) / 2 + df_spreads['fhqz3']
    df_spreads['fhqz5'] = (1 + df_spreads['fhqz4_5'])**2 / (1 + df_spreads['fhqz4']) - 1
    df_spreads['fhqz5_10'] = ((1 + df_spreads['yhqz10'])**10 / (1 + df_spreads['yhqz5'])**5)**(1/5) - 1
    df_spreads['fhqz10_15'] = ((1 + df_spreads['yhqz15'])**15 / (1 + df_spreads['yhqz10'])**10)**(1/5) - 1
    df_spreads['fhqz15_20'] = ((1 + df_spreads['yhqz20'])**20 / (1 + df_spreads['yhqz15'])**15)**(1/5) - 1
    df_spreads['fhqz20_30'] = ((1 + df_spreads['yhqz30'])**30 / (1 + df_spreads['yhqz20'])**20)**(1/10) - 1

print("Calculated HQ zero-coupon forward rates")


# Calculate HQ par forward rates
if 'yhqp2' in df_spreads.columns and 'yhqp5' in df_spreads.columns:
    df_spreads['fhqp2_5'] = ((1 + df_spreads['yhqp5'])**5 / (1 + df_spreads['yhqp2'])**2)**(1/3) - 1
    df_spreads['fhqp5_10'] = ((1 + df_spreads['yhqp10'])**10 / (1 + df_spreads['yhqp5'])**5)**(1/5) - 1
    df_spreads['fhqp10_30'] = ((1 + df_spreads['yhqp30'])**30 / (1 + df_spreads['yhqp10'])**10)**(1/20) - 1

    # Additional par yields
    df_spreads['yhqp6m'] = df_spreads.get('yhqz6m', np.nan)
    df_spreads['yhqp9m'] = df_spreads.get('yhqz9m', np.nan)
    df_spreads['yhqp1'] = df_spreads.get('yhqz1', np.nan)

    df_spreads['fhqp2'] = ((1 + df_spreads['yhqp2'])**2 / (1 + df_spreads['yhqp1']))**(1) - 1
    df_spreads['yhqp3'] = ((1 + df_spreads['yhqp2'])**2 * (1 + df_spreads['fhqp2_5']))**(1/3) - 1
    df_spreads['yhqp15'] = ((1 + df_spreads['yhqp10'])**10 * (1 + df_spreads['fhqp10_30'])**5)**(1/15) - 1
    df_spreads['yhqp20'] = ((1 + df_spreads['yhqp10'])**10 * (1 + df_spreads['fhqp10_30'])**10)**(1/20) - 1
    df_spreads['yhqp4'] = ((1 + df_spreads['yhqp3'])**3 * (1 + df_spreads['fhqp2_5'])**1)**(1/4) - 1
    df_spreads['yhqp6'] = ((1 + df_spreads['yhqp5'])**5 * (1 + df_spreads['fhqp5_10'])**1)**(1/6) - 1

print("Calculated HQ par forward rates")


# ============================================================
# DIAGNOSTIC: Check missing values in daily spread data
# ============================================================

print("="*70)
print("MISSING VALUE ANALYSIS FOR DAILY SPREADS")
print("="*70)

print("\n1. DAILY SPREAD DATA (df_spreads)")
print(f"   Total rows: {len(df_spreads)}")
print(f"   Date range: {df_spreads['daten'].min()} to {df_spreads['daten'].max()}")

# Check corporate bond spreads and yields
corp_vars = ['yaaa', 'yaa', 'ya', 'ybbb', 'ybb', 'yb', 'ybb_b', 
             's_aaa', 's_aa', 's_a', 's_bbb', 's_bb', 's_b', 's_bb_b']
print("\n   Missing values in corporate bond variables:")
for var in corp_vars:
    if var in df_spreads.columns:
        missing = df_spreads[var].isna().sum()
        pct = (missing / len(df_spreads) * 100).round(1)
        print(f"   {var:>8}: {missing:>6} ({pct:>5.1f}%)")

# Check HQ zero-coupon yields
hqz_vars = ['yhqz6m', 'yhqz1', 'yhqz2', 'yhqz3', 'yhqz5', 'yhqz10', 'yhqz15', 'yhqz20', 'yhqz30']
print("\n   Missing values in HQ zero-coupon yields:")
for var in hqz_vars:
    if var in df_spreads.columns:
        missing = df_spreads[var].isna().sum()
        pct = (missing / len(df_spreads) * 100).round(1)
        print(f"   {var:>8}: {missing:>6} ({pct:>5.1f}%)")

# Check HQ par yields
hqp_vars = ['yhqp6m', 'yhqp1', 'yhqp2', 'yhqp3', 'yhqp5', 'yhqp10', 'yhqp15', 'yhqp20', 'yhqp30']
print("\n   Missing values in HQ par yields:")
for var in hqp_vars:
    if var in df_spreads.columns:
        missing = df_spreads[var].isna().sum()
        pct = (missing / len(df_spreads) * 100).round(1)
        print(f"   {var:>8}: {missing:>6} ({pct:>5.1f}%)")

# Check mortgage rate
print("\n   Missing values in mortgage rate:")
if 'y30m' in df_spreads.columns:
    missing = df_spreads['y30m'].isna().sum()
    pct = (missing / len(df_spreads) * 100).round(1)
    print(f"   {'y30m':>8}: {missing:>6} ({pct:>5.1f}%)")


#############################################################################
# Save Spread Files
#############################################################################

# Save mean spreads
spread_cols = [col for col in df_spreads.columns if col.startswith(('yhqp', 'fhqp', 'ybb', 'ybbb', 'yb', 'yaaa', 'yaa', 'ya', 's_'))]
mean_spreads = df_spreads.groupby('date')[spread_cols].mean().reset_index()
mean_spreads = mean_spreads.rename(columns={col: f'mean_{col}' for col in spread_cols})
mean_spreads.to_parquet(INTER_DIR / 'mean_spreads.parquet')
print(f"Saved mean spreads to {INTER_DIR / 'mean_spreads.parquet'}")
print(f"Shape: {mean_spreads.shape}")
mean_spreads.head()


# Save daily spreads
y_cols = [col for col in df_spreads.columns if col.startswith('y') or col.startswith('f') or col.startswith('s_')]
daily_spread_cols = ['daten', 'datem', 'date'] + y_cols
daily_spreads = df_spreads[daily_spread_cols].copy()
daily_spreads.to_parquet(INTER_DIR / 'daily_spreads.parquet')
print(f"Saved daily spreads to {INTER_DIR / 'daily_spreads.parquet'}")
print(f"Shape: {daily_spreads.shape}")


# Save quarterly spreads (EOQ only)
eoq_spreads = df_spreads[df_spreads['daten'] == df_spreads['eoq_date']].copy()
spreads_eoq = eoq_spreads[['date'] + y_cols].copy()
spreads_eoq.to_parquet(INTER_DIR / 'spreads.parquet')
print(f"Saved quarterly spreads to {INTER_DIR / 'spreads.parquet'}")
print(f"Shape: {spreads_eoq.shape}")
spreads_eoq.tail()
