import requests
import time
from datetime import datetime

class DeribitClient:
    def __init__(self, client_id=None, client_secret=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://www.deribit.com/api/v2"
        self.token = None
        
        if client_id and client_secret:
            self.token = self._authenticate()

    def _authenticate(self):
        """Authenticate with Deribit API"""
        url = f"{self.base_url}/public/auth"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()['result']['access_token']
        except Exception as e:
            print(f"Authentication failed: {e}")
            return None

    def fetch_historical_prices(self, instrument, date_str):
        """Fetch historical OHLCV data for an instrument"""
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        start_ts = int(dt.timestamp() * 1000)
        end_ts = start_ts + (24 * 60 * 60 * 1000)
        
        url = f"{self.base_url}/public/get_tradingview_chart_data"
        params = {
            "instrument_name": instrument,
            "start_timestamp": start_ts,
            "end_timestamp": end_ts,
            "resolution": "60"
        }
        
        try:
            res = requests.get(url, params=params)
            res.raise_for_status()
            result = res.json().get('result')
            
            if result and result.get('status') == 'ok' and result.get('close'):
                return result
            return None
        except Exception as e:
            # print(f"Error fetching {instrument}: {e}")
            return None

    def get_instruments(self, currency, expired=False):
        """Get all option instruments for a currency"""
        url = f"{self.base_url}/public/get_instruments"
        params = {
            "currency": currency.upper(),
            "kind": "option",
            "expired": str(expired).lower()
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            instruments = response.json()['result']
            return [i['instrument_name'] for i in instruments]
        except Exception as e:
            print(f"Error fetching instruments: {e}")
            return []
    
    def get_ticker(self, instrument):
        """Fetch current ticker data including IV"""
        url = f"{self.base_url}/public/ticker"
        params = {"instrument_name": instrument}
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()['result']
        except Exception as e:
            # print(f"Error fetching ticker for {instrument}: {e}")
            return None
    
    def get_index_price(self, currency):
        """Get current BTC/ETH index price"""
        url = f"{self.base_url}/public/get_index_price"
        params = {"index_name": f"{currency.lower()}_usd"}
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()['result']['index_price']
        except Exception as e:
            print(f"Error fetching index price: {e}")
            return None
    
    def get_last_settlements_by_currency(self, currency, search_start_timestamp, count=20):
        """Get settlements around a specific time"""
        url = f"{self.base_url}/public/get_last_settlements_by_currency"
        params = {
            "currency": currency.upper(),
            "type": "settlement",
            "count": count,
            "search_start_timestamp": search_start_timestamp
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()['result']
        except Exception as e:
            print(f"Error fetching settlements: {e}")
            return None
    
    def get_order_book(self, instrument, depth=1):
        """Get order book for an instrument"""
        url = f"{self.base_url}/public/get_order_book"
        params = {
            "instrument_name": instrument,
            "depth": depth
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()['result']
        except Exception as e:
            return None
    
    def get_last_trades_by_instrument(self, instrument, start_timestamp, end_timestamp, count=100):
        """Get historical trades for an instrument"""
        url = f"{self.base_url}/public/get_last_trades_by_instrument"
        params = {
            "instrument_name": instrument,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "count": count,
            "include_old": "true"
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            result = response.json().get('result', {})
            return result.get('trades', [])
        except Exception as e:
            return []

    def get_last_trades_by_currency(self, currency, start_timestamp, end_timestamp, count=100):
        """Get historical trades for all instruments of a currency"""
        url = f"{self.base_url}/public/get_last_trades_by_currency"
        params = {
            "currency": currency.upper(),
            "kind": "option",
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "count": count,
            "include_old": "true"
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            result = response.json().get('result', {})
            return result.get('trades', [])
        except Exception as e:
            return []

    def get_historical_index_price(self, currency, timestamp):
        """
        Estimate historical index price from settlement or ticker data
        Note: This is an approximation
        """
        # Try to get from settlements near that time
        settlements = self.get_last_settlements_by_currency(
            currency, 
            search_start_timestamp=timestamp,
            count=10
        )
        
        if settlements and 'settlements' in settlements:
            for s in settlements['settlements']:
                if abs(s['timestamp'] - timestamp) < 3600000:  # Within 1 hour
                    return s.get('index_price')
        
        return None