import pandas as pd
import time
from datetime import datetime, timezone, timedelta
from deribit_api import DeribitClient
from data_utils import calculate_greeks, calculate_iv_from_price
from tqdm import tqdm
from collections import defaultdict

# Initialize client (public endpoints don't need auth)
client = DeribitClient()

def get_current_options_data(currency, limit=20):
    """Fetch current options data with Greeks"""
    spot_price = client.get_index_price(currency)
    if not spot_price:
        print("Failed to fetch spot price")
        return pd.DataFrame()
    
    print(f"{currency} Spot Price: ${spot_price:,.2f}")
    
    names = client.get_instruments(currency, expired=False)
    if not names:
        print("No instruments found")
        return pd.DataFrame()
    
    print(f"Found {len(names)} instruments, fetching {min(limit, len(names))}...")
    names = names[:limit]
    
    results = []
    for name in tqdm(names, desc="Processing"):
        ticker = client.get_ticker(name)
        if not ticker:
            continue
        
        iv = ticker.get('mark_iv')
        mark_price = ticker.get('mark_price')
        volume_usd = ticker.get('stats', {}).get('volume_usd', 0)
        open_interest = ticker.get('open_interest', 0)
        bid = ticker.get('best_bid_price', 0)
        ask = ticker.get('best_ask_price', 0)
        
        greeks = calculate_greeks(name, spot_price, iv)
        
        results.append({
            "instrument": name,
            "mark_price": mark_price,
            "bid": bid,
            "ask": ask,
            "volume_usd": volume_usd,
            "open_interest": open_interest,
            "iv": iv,
            "spot_price": spot_price,
            **greeks
        })
        
        time.sleep(0.1)
    
    return pd.DataFrame(results)

def get_live_trading_data(currency, minutes_back=60, limit=200):
    """
    Fetch recent trading data from last N minutes
    This uses actual trade data to reconstruct option prices and Greeks
    """
    print(f"[LIVE TRADES] Fetching trades from last {minutes_back} minutes...")
    
    # Get current spot price
    spot_price = client.get_index_price(currency)
    if not spot_price:
        print("✗ Could not fetch spot price")
        return pd.DataFrame()
    
    print(f"{currency} Spot Price: ${spot_price:,.2f}")
    
    # Calculate time window
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = now_ms - (minutes_back * 60 * 1000)
    
    # Fetch all trades in window
    print("Fetching trades...")
    all_trades = client.get_last_trades_by_currency(
        currency,
        start_timestamp=start_ms,
        end_timestamp=now_ms,
        count=1000
    )
    
    if not all_trades:
        print("✗ No trades found")
        return pd.DataFrame()
    
    print(f"Found {len(all_trades)} trades")
    
    # Aggregate by instrument
    instrument_data = defaultdict(lambda: {
        "prices": [],
        "volumes": [],
        "timestamps": []
    })
    
    for trade in all_trades:
        inst = trade['instrument_name']
        instrument_data[inst]["prices"].append(trade['price'])
        instrument_data[inst]["volumes"].append(trade['amount'])
        instrument_data[inst]["timestamps"].append(trade['timestamp'])
    
    print(f"Trades across {len(instrument_data)} unique instruments")
    
    # Build results
    results = []
    instruments_sorted = sorted(
        instrument_data.items(),
        key=lambda x: sum(x[1]["volumes"]),
        reverse=True
    )[:limit]
    
    for instrument, data in tqdm(instruments_sorted, desc="Calculating Greeks"):
        prices = data["prices"]
        volumes = data["volumes"]
        timestamps = data["timestamps"]
        
        # Use volume-weighted average price
        total_vol = sum(volumes)
        vwap = sum(p * v for p, v in zip(prices, volumes)) / total_vol if total_vol > 0 else sum(prices) / len(prices)
        
        latest_price = prices[-1]  # Most recent trade
        
        # Calculate IV from VWAP
        iv = calculate_iv_from_price(instrument, spot_price, vwap)
        
        if iv and 0 < iv < 500:  # Sanity check
            greeks = calculate_greeks(instrument, spot_price, iv)
        else:
            greeks = {"delta": None, "gamma": None, "vega": None, "theta": None}
            iv = None
        
        # Get last trade time
        last_trade_dt = datetime.fromtimestamp(timestamps[-1] / 1000, tz=timezone.utc)
        
        results.append({
            "instrument": instrument,
            "vwap": vwap,
            "latest_price": latest_price,
            "num_trades": len(prices),
            "total_volume": total_vol,
            "last_trade": last_trade_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "spot_price": spot_price,
            "calculated_iv": iv,
            **greeks
        })
    
    return pd.DataFrame(results)

def get_settlement_data(currency, date_str=None, days_back=90):
    """
    Get settlement data 
    If no date specified, get recent settlements
    """
    if date_str:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        dt = dt.replace(hour=8, minute=0, second=0, tzinfo=timezone.utc)
        timestamp_ms = int(dt.timestamp() * 1000)
        print(f"[SETTLEMENT] Fetching settlement data around {date_str}")
    else:
        # Get recent settlements
        dt = datetime.now(timezone.utc) - timedelta(days=days_back)
        timestamp_ms = int(dt.timestamp() * 1000)
        print(f"[SETTLEMENT] Fetching settlements from last {days_back} days")
    
    settlements = client.get_last_settlements_by_currency(
        currency, 
        search_start_timestamp=timestamp_ms,
        count=1000
    )
    
    if not settlements or 'settlements' not in settlements:
        print("No settlement data found")
        return pd.DataFrame()
    
    print(f"Found {len(settlements['settlements'])} settlements")
    
    results = []
    for settlement in settlements['settlements']:
        settle_dt = datetime.fromtimestamp(settlement['timestamp'] / 1000, tz=timezone.utc)
        settle_date = settle_dt.strftime("%Y-%m-%d")
        
        # If specific date was requested, filter
        if date_str:
            target_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_diff = abs((settle_dt - target_dt).days)
            
            if days_diff > 1:
                continue
        
        results.append({
            "instrument": settlement['instrument_name'],
            "settlement_date": settle_date,
            "settlement_time": settle_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "settlement_type": settlement.get('type'),
            "index_price": settlement.get('index_price'),
            "mark_price": settlement.get('mark_price'),
            "session_profit_loss": settlement.get('session_profit_loss'),
        })
    
    df = pd.DataFrame(results)
    
    # Sort by date
    if not df.empty:
        df = df.sort_values('settlement_time', ascending=False)
    
    return df

def snapshot_market(currency, limit=None):
    """
    Take a complete market snapshot - all active options with full data
    This is the most comprehensive current data fetch
    """
    print(f"[SNAPSHOT] Taking full market snapshot for {currency}...")
    
    spot_price = client.get_index_price(currency)
    if not spot_price:
        print("✗ Could not fetch spot price")
        return pd.DataFrame()
    
    print(f"{currency} Spot Price: ${spot_price:,.2f}")
    
    names = client.get_instruments(currency, expired=False)
    if not names:
        print("✗ No instruments found")
        return pd.DataFrame()
    
    if limit:
        names = names[:limit]
    
    print(f"Fetching data for {len(names)} instruments...")
    
    results = []
    for name in tqdm(names, desc="Processing"):
        ticker = client.get_ticker(name)
        if not ticker:
            continue
        
        # Parse instrument details
        parts = name.split('-')
        expiry = parts[1] if len(parts) >= 2 else None
        strike = parts[2] if len(parts) >= 3 else None
        option_type = parts[3] if len(parts) >= 4 else None
        
        iv = ticker.get('mark_iv')
        mark_price = ticker.get('mark_price')
        underlying_price = ticker.get('underlying_price')
        volume_usd = ticker.get('stats', {}).get('volume_usd', 0)
        volume = ticker.get('stats', {}).get('volume', 0)
        open_interest = ticker.get('open_interest', 0)
        bid = ticker.get('best_bid_price', 0)
        ask = ticker.get('best_ask_price', 0)
        bid_size = ticker.get('best_bid_amount', 0)
        ask_size = ticker.get('best_ask_amount', 0)
        last_price = ticker.get('last_price', 0)
        
        greeks = calculate_greeks(name, spot_price, iv)
        
        results.append({
            "instrument": name,
            "expiry": expiry,
            "strike": strike,
            "type": option_type,
            "mark_price": mark_price,
            "last_price": last_price,
            "bid": bid,
            "ask": ask,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "volume": volume,
            "volume_usd": volume_usd,
            "open_interest": open_interest,
            "iv": iv,
            "spot_price": spot_price,
            "underlying_price": underlying_price,
            **greeks
        })
        
        time.sleep(0.05)  # Faster rate for bulk fetch
    
    return pd.DataFrame(results)

def test_api_limits():
    """Test what data is actually available"""
    print("="*80)
    print("TESTING DERIBIT API DATA AVAILABILITY")
    print("="*80)
    
    # Test 1: Current data
    print("\n[TEST 1] Current spot price:")
    spot = client.get_index_price("BTC")
    print(f"✓ BTC Spot: ${spot:,.2f}" if spot else "✗ Failed")
    
    # Test 2: Recent settlements
    print("\n[TEST 2] Recent settlements:")
    now_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    settlements = client.get_last_settlements_by_currency("BTC", now_ts, count=10)
    if settlements and 'settlements' in settlements:
        print(f"✓ Found {len(settlements['settlements'])} recent settlements")
        if settlements['settlements']:
            latest = settlements['settlements'][0]
            settle_dt = datetime.fromtimestamp(latest['timestamp']/1000, tz=timezone.utc)
            print(f"  Latest: {latest['instrument_name']} on {settle_dt.strftime('%Y-%m-%d %H:%M')}")
    else:
        print("✗ No settlements found")
    
    # Test 3: Trades data
    print("\n[TEST 3] Recent trades:")
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    hour_ago_ms = now_ms - (3600 * 1000)
    trades = client.get_last_trades_by_currency("BTC", hour_ago_ms, now_ms, count=10)
    print(f"✓ Found {len(trades)} trades in last hour" if trades else "✗ No trades found")
    if trades:
        print(f"  Sample instrument: {trades[0]['instrument_name']}")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    import sys
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "current"
    
    if mode == "current":
        df = get_current_options_data("BTC", limit=20)
        output_file = "options_current.csv"
        
    elif mode == "snapshot":
        # Full market snapshot
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        df = snapshot_market("BTC", limit=limit)
        output_file = "options_snapshot_full.csv"
        
    elif mode == "live":
        # Recent trades analysis
        minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        df = get_live_trading_data("BTC", minutes_back=minutes, limit=200)
        output_file = f"options_live_{minutes}min.csv"
        
    elif mode == "settlement":
        # Settlement data
        date = sys.argv[2] if len(sys.argv) > 2 else None
        df = get_settlement_data("BTC", date_str=date, days_back=90)
        output_file = f"options_settlement_{date if date else 'recent'}.csv"
    
    elif mode == "test":
        # Test API capabilities
        test_api_limits()
        sys.exit(0)
    
    else:
        print("Usage: uv run main.py [mode] [options]")
        print("\nModes:")
        print("  current              - Quick fetch of 20 options with Greeks")
        print("  snapshot [limit]     - Full market snapshot (all options)")
        print("  live [minutes]       - Reconstruct from recent trades (default 60min)")
        print("  settlement [date]    - Get settlement history")
        print("  test                 - Test API capabilities")
        print("\nExamples:")
        print("  uv run main.py current")
        print("  uv run main.py snapshot 100")
        print("  uv run main.py snapshot         # All instruments")
        print("  uv run main.py live 30          # Last 30 minutes")
        print("  uv run main.py settlement       # Recent settlements")
        print("  uv run main.py settlement 2026-01-26")
        sys.exit(1)
    
    if not df.empty:
        print("\n" + "="*120)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_rows', 20)
        print(df.head(20))
        
        df.to_csv(output_file, index=False)
        print(f"\n✓ Saved {len(df)} rows to {output_file}")
    else:
        print("✗ No data retrieved")