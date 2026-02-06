from py_vollib.black_scholes.greeks.numerical import delta, gamma, vega, theta
from py_vollib.black_scholes import black_scholes
from py_vollib.black_scholes.implied_volatility import implied_volatility
from datetime import datetime
import math

def calculate_greeks(instrument, spot_price, iv, snapshot_date_str=None):
    """
    Calculate Greeks for an option
    
    Args:
        instrument: Deribit instrument name (e.g., BTC-27MAR26-80000-C)
        spot_price: Current BTC spot price
        iv: Implied volatility (as percentage, e.g., 65.5)
        snapshot_date_str: Optional date string for historical calculation
    """
    # Parse instrument
    parts = instrument.split('-')
    if len(parts) != 4:
        return {"delta": 0, "gamma": 0, "vega": 0, "theta": 0, "error": "Invalid instrument format"}
    
    strike = float(parts[2])
    option_type = 'c' if parts[3] == 'C' else 'p'
    
    # Calculate time to expiry
    expiry_str = parts[1] + " 08:00:00"
    try:
        expiry_dt = datetime.strptime(expiry_str, "%d%b%y %H:%M:%S")
        
        if snapshot_date_str:
            if ' ' in snapshot_date_str:
                now = datetime.strptime(snapshot_date_str, "%Y-%m-%d %H:%M:%S")
            else:
                now = datetime.strptime(snapshot_date_str, "%Y-%m-%d")
        else:
            now = datetime.utcnow()
        
        time_diff = (expiry_dt - now).total_seconds()
        
        if time_diff <= 0:
            return {"delta": 0, "gamma": 0, "vega": 0, "theta": 0, "expired": True}
        
        t = time_diff / (365.25 * 24 * 3600)
        
    except Exception as e:
        return {"delta": 0, "gamma": 0, "vega": 0, "theta": 0, "error": f"Date parse error: {e}"}

    # Validate IV
    if not iv or iv <= 0:
        return {"delta": 0, "gamma": 0, "vega": 0, "theta": 0, "error": "Invalid IV"}

    sigma = iv / 100
    r = 0.05  # Risk-free rate

    # Calculate Greeks
    try:
        return {
            "delta": round(delta(option_type, spot_price, strike, t, r, sigma), 4),
            "gamma": round(gamma(option_type, spot_price, strike, t, r, sigma), 6),
            "vega": round(vega(option_type, spot_price, strike, t, r, sigma), 4),
            "theta": round(theta(option_type, spot_price, strike, t, r, sigma), 4)
        }
    except Exception as e:
        return {"delta": 0, "gamma": 0, "vega": 0, "theta": 0, "error": f"Greeks calc error: {e}"}

def calculate_iv_from_price(instrument, spot_price, option_price, snapshot_date_str=None):
    """
    Back-calculate implied volatility from option price
    """
    parts = instrument.split('-')
    if len(parts) != 4:
        return None
    
    strike = float(parts[2])
    option_type = 'c' if parts[3] == 'C' else 'p'
    
    # Calculate time to expiry
    expiry_str = parts[1] + " 08:00:00"
    try:
        expiry_dt = datetime.strptime(expiry_str, "%d%b%y %H:%M:%S")
        
        if snapshot_date_str:
            if ' ' in snapshot_date_str:
                now = datetime.strptime(snapshot_date_str, "%Y-%m-%d %H:%M:%S")
            else:
                now = datetime.strptime(snapshot_date_str, "%Y-%m-%d")
        else:
            now = datetime.utcnow()
        
        time_diff = (expiry_dt - now).total_seconds()
        
        if time_diff <= 0:
            return None
        
        t = time_diff / (365.25 * 24 * 3600)
        
    except Exception as e:
        return None

    r = 0.05
    
    # Convert Deribit price (in BTC) to USD
    option_price_usd = option_price * spot_price
    
    # Calculate IV
    try:
        iv = implied_volatility(option_price_usd, spot_price, strike, t, r, option_type)
        return iv * 100  # Convert to percentage
    except Exception as e:
        return None