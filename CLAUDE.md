# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

Downloads corporate credit yields, spreads, and the HQM corporate credit curve from FRED, processes it into standardized formats with forward rates and interpolated maturities, and saves as Parquet files at multiple frequencies.

## Commands

```bash
# Setup
pip install -r requirements.txt
cp .env.example .env     # Then add FRED API key

# Full pipeline
python 01_download.py       # Download from FRED
python 02_parse.py          # Process and calculate forward rates
python 03_summarize.py      # Summarize output files
```

## Data Sources

- **ICE BofA Corporate Credit Indices** (FRED): Yields and option-adjusted spreads for AAA, AA, A, BBB, BB, B ratings
- **HQM Corporate Credit Curve** (FRED): High Quality Market corporate bond yields at various maturities
- **Mortgage Rates** (FRED): 30-year, 15-year, and jumbo mortgage rates

## File Structure

```
data_credit/
├── 01_download.py          # Downloads raw data from FRED API
├── 02_parse.py             # Processes data, renames variables, calculates forward rates
├── 03_summarize.py         # Summarizes output files
├── requirements.txt        # Python dependencies
├── .env.example            # Template for API key
├── .env                    # Your FRED API key (not committed)
└── data/
    ├── raw/                # Downloaded data
    │   └── fred_data.parquet
    └── processed/          # Final files with renamed variables + metadata
        └── *.parquet
```

## Output Files

### Corporate Credit Ratings (`*_rating.parquet`)
- `daily_rating` - All trading days
- `monthly_rating` - End of month
- `quarterly_rating` - End of quarter
- `quarterly_avg_rating` - Quarterly averages

### HQM Curve (`*_curve.parquet`)
- `monthly_curve` - Monthly averages (FRED data is already monthly averaged)
- `quarterly_curve` - Quarterly averages (computed from monthly)

### Mortgage Rates (`*_mtgrates.parquet`)
- `weekly_mtgrates` - Weekly data
- `monthly_mtgrates` - End of month
- `quarterly_mtgrates` - End of quarter
- `quarterly_avg_mtgrates` - Quarterly averages

## Key Variables

### Corporate Credit Yields (decimal format)
| Variable | Description |
|----------|-------------|
| `y_aaa`, `y_aa`, `y_a`, `y_bbb`, `y_bb`, `y_b` | Effective yields by rating |
| `y_bb_b` | Average of BB and B yields |
| `s_aaa`, `s_aa`, `s_a`, `s_bbb`, `s_bb`, `s_b` | Option-adjusted spreads |
| `s_bb_b` | Average of BB and B spreads |

### HQM Curve Yields (decimal format)
| Variable | Description |
|----------|-------------|
| `hqm_zero_6m`, `hqm_zero_1y`, ..., `hqm_zero_30y` | Zero-coupon yields at various maturities |
| `hqm_par_2y`, `hqm_par_5y`, `hqm_par_10y`, `hqm_par_30y` | Par yields |
| `fwd_zero_*`, `fwd_par_*` | Forward rates |

### Mortgage Rates (decimal format)
| Variable | Description |
|----------|-------------|
| `ym_30` | 30-year fixed mortgage rate |
| `ym_15` | 15-year fixed mortgage rate |
| `ym_30_jumbo` | 30-year jumbo mortgage rate |

## Processing Logic

1. **Download**: Fetches all series from FRED API starting from 1980
2. **Rename**: Maps FRED series IDs to meaningful variable names (defined in `02_parse.py`)
3. **Convert**: Transforms percentages to decimals (divide by 100)
4. **Forward Fill**: Fills missing values using up to 7-day lookback (post-1996 for corporate)
5. **Forward Rates**: Calculates forward rates from spot yields
6. **Interpolate**: Creates interpolated maturities (9m, 3yr, 4yr, 6yr, 15yr, 20yr)
7. **Filter**: Drops rows where all data columns are null (each file type filtered independently)
8. **Aggregate**: Saves at multiple frequencies (daily, monthly, quarterly, quarterly avg)

## Development Notes

- All yields and spreads are stored as decimals (e.g., 0.05 for 5%)
- Date columns: `daten` (datetime), `datem` (month period string), `dateq` (quarter period string)
- Variable metadata stored in parquet file schema metadata
- Variable definitions (FRED ID → name mapping) are in `VARIABLE_DEFINITIONS` dict in `02_parse.py`
- FRED API key required - get one at https://fred.stlouisfed.org/docs/api/api_key.html
