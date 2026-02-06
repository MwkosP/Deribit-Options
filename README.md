# Deribit Options Data Retriever & Greeks Calculator

## Project Overview

This project fetches BTC options data from Deribit's API and calculates option Greeks (Delta, Gamma, Vega, Theta) using the Black-Scholes model. It provides both real-time market snapshots and historical data reconstruction capabilities.

**Repository:** https://github.com/MwkosP/Deribit-Options

## Quick Start

```bash
# Install dependencies with uv
uv add requests pandas py-vollib tqdm

# Test API connectivity
uv run main.py test

# Get current market data (20 options)
uv run main.py current

# Get complete market snapshot (all ~900+ options)
uv run main.py snapshot

# Get live trading data from last hour
uv run main.py live 60

# Get recent historical data
uv run main.py recent 1

# Get settlement history
uv run main.py settlement
```

## Architecture

### Core Components

```
deribit-options/
├── deribit_api.py      # Deribit API client wrapper
├── data_utils.py       # Greeks calculation & IV reconstruction
├── main.py             # Main CLI interface
└── outputs/            # CSV outputs saved here
```

### File Descriptions

#### `deribit_api.py`
Handles all Deribit API interactions. Uses public endpoints (no authentication required for read-only access).

**Key Methods:**
- `get_instruments(currency, expired)` - List all option instruments
- `get_ticker(instrument)` - Get current price, IV, volume, OI for one option
- `get_index_price(currency)` - Get BTC/ETH spot price
- `get_last_trades_by_currency()` - Recent trades across all options
- `get_last_settlements_by_currency()` - Settlement history
- `fetch_historical_prices()` - Historical OHLCV chart data

#### `data_utils.py`
Greeks calculations using py_vollib library.

**Key Functions:**
- `calculate_greeks(instrument, spot_price, iv, snapshot_date_str)` 
  - Parses instrument name (e.g., BTC-6FEB26-60000-C)
  - Calculates time to expiry
  - Computes Delta, Gamma, Vega, Theta using Black-Scholes
  
- `calculate_iv_from_price(instrument, spot_price, option_price, snapshot_date_str)`
  - Back-calculates implied volatility from option price
  - Used for historical data where IV isn't provided by API
  - Uses Newton-Raphson method via py_vollib

#### `main.py`
CLI interface with multiple modes for different use cases.

**Available Modes:**
1. **current** - Quick snapshot of 20 options
2. **snapshot** - Full market snapshot (all active options)
3. **live** - Reconstruct from recent trades
4. **recent** - Historical data from N days ago
5. **settlement** - Settlement history
6. **test** - API connectivity test

## Command Reference

| Command | Purpose | Output File | Data Points | Greeks |
|---------|---------|-------------|-------------|--------|
| `uv run main.py test` | Test API connectivity | None | N/A | ❌ |
| `uv run main.py current` | 20 options quick check | `options_current.csv` | ~20 | ✅ |
| `uv run main.py snapshot` | ALL active options | `options_snapshot_full.csv` | ~900+ | ✅ |
| `uv run main.py snapshot 100` | First 100 options | `options_snapshot_full.csv` | 100 | ✅ |
| `uv run main.py live 60` | Last 60min trades | `options_live_60min.csv` | Varies | ✅ |
| `uv run main.py recent 1` | 1 day ago | `options_recent_1days.csv` | ~100 | ⚠️ |
| `uv run main.py settlement` | Last 90 days | `options_settlement_recent.csv` | Varies | ❌ |

**Legend:**
- ✅ Full Greeks (from Deribit IV)
- ⚠️ Partial Greeks (reconstructed IV, may have NaN)
- ❌ No Greeks (settlement data only)

## Data Schema

### Snapshot Mode Output

```csv
instrument,expiry,strike,type,mark_price,last_price,bid,ask,bid_size,ask_size,
volume,volume_usd,open_interest,iv,spot_price,underlying_price,
delta,gamma,vega,theta
```

**Key Fields:**
- `instrument`: Full name (e.g., BTC-6FEB26-60000-C)
- `expiry`: Expiry date code (e.g., 6FEB26)
- `strike`: Strike price
- `type`: C (Call) or P (Put)
- `mark_price`: Deribit's fair value (in BTC)
- `iv`: Implied volatility (%)
- `spot_price`: Current BTC price (USD)
- `delta`: Rate of change of option price w.r.t. underlying
- `gamma`: Rate of change of delta
- `vega`: Sensitivity to volatility (per 1% IV change)
- `theta`: Time decay (per day)

### Live Trades Output

```csv
instrument,vwap,latest_price,num_trades,total_volume,last_trade,
spot_price,calculated_iv,delta,gamma,vega,theta
```

**Key Fields:**
- `vwap`: Volume-weighted average price from trades
- `num_trades`: Number of trades in time window
- `total_volume`: Total volume traded (BTC)
- `calculated_iv`: IV back-calculated from VWAP

## Greeks Calculation Details

### Black-Scholes Model

Using `py_vollib` library with the following parameters:

```python
option_type = 'c' or 'p'  # Call or Put
S = spot_price            # Current BTC price
K = strike                # Strike price
t = T / 365.25           # Time to expiry (years)
r = 0.05                 # Risk-free rate (5%)
sigma = iv / 100         # Volatility (decimal)
```

### Time to Expiry Calculation

Deribit options expire at **08:00 UTC** on the expiry date:

```python
expiry_str = "6FEB26 08:00:00"
expiry_dt = datetime.strptime(expiry_str, "%d%b%y %H:%M:%S")
time_to_expiry = (expiry_dt - now).total_seconds() / (365.25 * 24 * 3600)
```

### IV Reconstruction

For historical data where Deribit doesn't provide IV:

1. Get historical option price from chart data
2. Convert from BTC to USD: `price_usd = price_btc * spot_price`
3. Use `implied_volatility()` to solve for sigma
4. Newton-Raphson iterative solver finds IV that matches observed price

**Limitations:**
- May fail for deep OTM options (low prices)
- Requires accurate spot price estimate
- Near expiry, numerical instability can occur
- Returns `None` → Greeks become `NaN` in output

## API Limitations & Workarounds

### What Works ✅

1. **Current data** - Full access to all active options
2. **Recent trades** - Last few hours of trade history
3. **Settlements** - 90 days of settlement history
4. **Chart data** - Limited historical OHLCV (spotty beyond 7 days)

### What Doesn't Work ❌

1. **Old historical trades** - Public API only stores recent trades
2. **Historical IV directly** - Must reconstruct from prices
3. **Tick-by-tick data** - Not available via public API
4. **Historical order book** - Not accessible

### Workarounds

**For historical Greeks:**
- Run `snapshot` daily and build your own database
- Use `recent N` for last ~7 days (limited reliability)
- Use settlement data for expired options analysis

**For better historical data:**
- Consider Deribit's authenticated API (more data access)
- Use historical data export service (contact Deribit)
- Subscribe to real-time feed and log locally

## Common Use Cases

### 1. Daily Market Snapshot

```bash
# Run daily via cron/scheduler
uv run main.py snapshot
# Rename with timestamp
mv options_snapshot_full.csv snapshots/snapshot_$(date +%Y%m%d).csv
```

### 2. Trading Activity Analysis

```bash
# What's been trading in last hour?
uv run main.py live 60

# Filter in Python
df = pd.read_csv('options_live_60min.csv')
active = df[df['num_trades'] > 10].sort_values('total_volume', ascending=False)
```

### 3. Greeks Surface Analysis

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('options_snapshot_full.csv')

# Filter for specific expiry
march_options = df[df['expiry'] == '28MAR26']

# Calls only
calls = march_options[march_options['type'] == 'C']

# Plot delta vs strike
plt.plot(calls['strike'].astype(float), calls['delta'])
plt.xlabel('Strike')
plt.ylabel('Delta')
plt.title('Call Delta Surface - March 28 Expiry')
plt.show()
```

### 4. Volatility Smile

```python
df = pd.read_csv('options_snapshot_full.csv')

# Single expiry
feb6 = df[df['expiry'] == '6FEB26']

# Plot IV vs strike
plt.scatter(feb6['strike'].astype(float), feb6['iv'], 
            c=['red' if t=='C' else 'blue' for t in feb6['type']])
plt.xlabel('Strike')
plt.ylabel('Implied Volatility (%)')
plt.title('Volatility Smile - Feb 6 Expiry')
plt.show()
```

### 5. Open Interest Heatmap

```python
import seaborn as sns

df = pd.read_csv('options_snapshot_full.csv')

# Pivot table
pivot = df.pivot_table(
    values='open_interest',
    index='strike',
    columns='expiry',
    aggfunc='sum'
)

sns.heatmap(pivot, cmap='YlOrRd')
plt.title('Open Interest Heatmap')
plt.show()
```

## Error Handling

### Common Issues

**1. No data retrieved**
```
✗ No data retrieved
```
**Cause:** API returned empty results  
**Fix:** Try different date/time, check API status, use `test` mode

**2. Greeks show NaN**
```
calculated_iv: NaN
delta: NaN
```
**Cause:** IV reconstruction failed (deep OTM, low price, near expiry)  
**Fix:** Filter out NaN rows, use only ATM/ITM options, or get data closer to trade time

**3. Historical data empty**
```
✗ No instruments found for this date
```
**Cause:** Date too far back, no chart data available  
**Fix:** Use more recent date (< 7 days), or use `settlement` mode

### Debugging Steps

```bash
# 1. Test API
uv run main.py test

# 2. Check current data works
uv run main.py current

# 3. Try recent trades
uv run main.py live 60

# 4. If all fail, check:
# - Internet connection
# - Deribit API status (https://status.deribit.com)
# - Rate limiting (add more time.sleep() calls)
```

## Performance Notes

**Snapshot mode timing:**
- ~900 options at 0.05s each = ~45 seconds
- With rate limiting: 0.1s each = ~90 seconds
- Network latency adds overhead

**Optimization tips:**
```python
# Reduce sleep time for faster fetches (watch for rate limits)
time.sleep(0.05)  # Instead of 0.1

# Limit results for testing
uv run main.py snapshot 100  # First 100 only

# Use multiprocessing for large batches
from concurrent.futures import ThreadPoolExecutor
```

## Development Context

### Dependencies

```toml
[dependencies]
requests = "*"      # HTTP client for API calls
pandas = "*"        # Data manipulation
py-vollib = "*"     # Black-Scholes Greeks calculations
tqdm = "*"          # Progress bars
```

### Why These Choices?

- **py_vollib**: Industry-standard library for option pricing, well-tested
- **requests**: Simple, reliable HTTP client
- **pandas**: Best for tabular data, CSV I/O
- **No authentication**: Public endpoints sufficient for read-only access

### Potential Extensions

1. **Real-time streaming** - WebSocket connection for live updates
2. **Database storage** - PostgreSQL/TimescaleDB for historical data
3. **Visualization dashboard** - Streamlit/Dash for interactive charts
4. **Alert system** - Notify on unusual IV, volume, or Greek changes
5. **Strategy backtesting** - Test option strategies on historical data
6. **Multi-currency** - Add ETH, SOL options support
7. **Order execution** - Integrate authenticated API for trading

### Code Quality Notes

**Current state:**
- ✅ Modular design (API, utils, main separated)
- ✅ Error handling with try/except
- ✅ Progress bars for UX
- ✅ CSV outputs for portability

**Potential improvements:**
- Add unit tests (pytest)
- Type hints throughout
- Config file for parameters (r, time zones)
- Logging instead of print statements
- asyncio for concurrent API calls

## Contributing

When adding features or fixing bugs:

1. **Test with `test` mode first** - Ensure API access works
2. **Handle None/NaN gracefully** - IV calculation can fail
3. **Respect rate limits** - Add delays between requests
4. **Document in CLAUDE.md** - Keep this file updated
5. **CSV schema stability** - Don't break existing column names

## Troubleshooting FAQ

**Q: Why are some Greeks NaN?**  
A: IV calculation failed. Usually deep OTM options with prices too low for numerical solver.

**Q: Can I get data from 6 months ago?**  
A: Not reliably via public API. Settlement data goes back 90 days. For older data, need daily snapshots or paid data service.

**Q: How accurate are the Greeks?**  
A: Very accurate for current data (using Deribit's IV). Historical Greeks are approximations based on reconstructed IV.

**Q: Why is historical data spotty?**  
A: Deribit's public API has limited historical storage. Chart data endpoint is unreliable beyond ~7 days.

**Q: Can I trade using this?**  
A: This is read-only. For trading, need authenticated API and order endpoints (not included).

**Q: What's the rate limit?**  
A: Not officially documented for public endpoints. We use 0.1s delays to be safe. Adjust if needed.

## License & Disclaimer

This is an educational/research tool. Not financial advice. Use at your own risk.

Options trading involves significant risk. Past performance doesn't indicate future results.

Deribit® is a registered trademark. This project is not affiliated with or endorsed by Deribit.

---

**Last Updated:** February 6, 2026  
**Maintainer:** Contact via GitHub issues  
**Version:** 1.0.0
