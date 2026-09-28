# Corporate Credit Data Pipeline

Downloads corporate credit yields, spreads, and the HQM corporate credit curve from FRED, processes it into standardized formats with forward rates and interpolated maturities, and saves as Parquet files at multiple frequencies.

## Features

- Downloads ICE BofA corporate bond yields and spreads (AAA through B ratings)
- Downloads Treasury HQM corporate credit curve data
- Downloads mortgage rates (30-year, 15-year, jumbo)
- Downloads the Gilchrist-Zakrajsek credit spread and excess bond premium (Federal Reserve Board)
- Calculates forward rates from spot yields
- Interpolates missing maturities
- Outputs data at multiple frequencies: daily, monthly, quarterly, and quarterly average
- Filters out rows with no data (each file type starts when data becomes available)
- Stores variable descriptions as parquet metadata

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

1. Get a free FRED API key from https://fred.stlouisfed.org/docs/api/api_key.html
2. Create your environment file:
   ```bash
   cp .env.example .env
   ```
3. Add your API key to `.env`:
   ```
   FRED_API_KEY=your_api_key_here
   ```

## Usage

Run the full pipeline:

```bash
python 01_download.py    # Download data from FRED
python 02_parse.py       # Process and calculate forward rates
python 03_summarize.py   # View summary with column availability by date range
```

## Data Sources

| Source | Series | Description |
|--------|--------|-------------|
| FRED | BAMLC0A1CAAA, BAMLC0A1CAAAEY, etc. | ICE BofA Corporate Bond Indices |
| FRED | HQMCB6MT, HQMCB1YR, etc. | HQM Corporate Bond Yields |
| FRED | MORTGAGE30US, MORTGAGE15US, OBMMIJUMBO30YF | Mortgage Rates |
| Federal Reserve Board | [ebp_csv.csv](https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv) | Gilchrist-Zakrajsek credit spread and excess bond premium, monthly from 1973 |

## Output Files

All output files are saved to `data/processed/` in Parquet format with embedded metadata.

### Corporate Credit Ratings
| File | Description |
|------|-------------|
| `daily_rating.parquet` | All trading days |
| `monthly_rating.parquet` | End of month values |
| `quarterly_rating.parquet` | End of quarter values |
| `quarterly_avg_rating.parquet` | Quarterly averages |

### HQM Curve
| File | Description |
|------|-------------|
| `monthly_curve.parquet` | Monthly averages (FRED data is already averaged) |
| `quarterly_curve.parquet` | Quarterly averages (from monthly) |

### Mortgage Rates
| File | Description |
|------|-------------|
| `weekly_mtgrates.parquet` | Weekly data |
| `monthly_mtgrates.parquet` | End of month values |
| `quarterly_mtgrates.parquet` | End of quarter values |
| `quarterly_avg_mtgrates.parquet` | Quarterly averages |

### Gilchrist-Zakrajsek Spread and Excess Bond Premium
| File | Description |
|------|-------------|
| `monthly_gz.parquet` | Monthly (as published) |
| `quarterly_gz.parquet` | Last month of each quarter |
| `quarterly_avg_gz.parquet` | Quarterly averages |

The Board re-estimates the full history with each release, so the latest vintage replaces the
previous one; each pull is also kept in `data/raw/gz_ebp_YYYYMMDD.csv`.

## Variables

### Corporate Credit (decimal format)
- `y_aaa`, `y_aa`, `y_a`, `y_bbb`, `y_bb`, `y_b` - Effective yields by rating
- `s_aaa`, `s_aa`, `s_a`, `s_bbb`, `s_bb`, `s_b` - Option-adjusted spreads
- `y_bb_b`, `s_bb_b` - BB/B averages

### HQM Curve (decimal format)
- `hqm_zero_6m`, `hqm_zero_1y`, `hqm_zero_2y`, ..., `hqm_zero_30y` - Zero-coupon yields
- `hqm_par_2y`, `hqm_par_5y`, `hqm_par_10y`, `hqm_par_30y` - Par yields
- `fwd_zero_*`, `fwd_par_*` - Forward rates

### Mortgage Rates (decimal format)
- `ym_30` - 30-year fixed rate
- `ym_15` - 15-year fixed rate
- `ym_30_jumbo` - 30-year jumbo rate

### Gilchrist-Zakrajsek (decimal format, except the probability)
- `gz_spread` - GZ credit spread
- `ebp` - Excess bond premium
- `recession_prob` - Estimated probability of recession over the next 12 months (0-1)

## Requirements

- Python 3.8+
- pandas
- pyarrow
- fredapi
- python-dotenv
- numpy
- requests

## License

MIT
