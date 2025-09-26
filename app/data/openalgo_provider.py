# app/data/openalgo_provider.py
"""
OpenAlgo data provider for fetching historical market data using the OpenAlgo Python package.
"""

from openalgo import api
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import time
import pandas as pd
from ..models.market_data import Candle, Quote
from ..models.config import OpenAlgoConfig
from .cache_manager import CacheManager


logger = logging.getLogger(__name__)


class OpenAlgoDataProvider:
    """
    Data provider for OpenAlgo API using the official OpenAlgo Python package.
    """
    
    def __init__(self, config: OpenAlgoConfig):
        """
        Initialize OpenAlgo data provider.
        
        Args:
            config: OpenAlgo configuration
        """
        self.config = config
        
        # Initialize OpenAlgo client
        self.client = api(
            api_key=config.api_key,
            host=config.base_url
        )
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests
        
        # Cache settings
        self.force_cache_use = config.force_cache_use
        self.cache_max_age_hours = config.cache_max_age_hours
        
        # Initialize cache manager
        self.cache = CacheManager()
        
        logger.info(f"OpenAlgo provider initialized: {config.base_url}")
    
    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def get_historical_data(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        limit: int = 1000
    ) -> List[Candle]:
        """
        Fetch historical OHLCV data using OpenAlgo.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            timeframe: Timeframe (1m, 5m, 15m, 30m, 1h, 1d)
            start: Start datetime
            end: End datetime
            limit: Maximum number of candles per request
            
        Returns:
            List of Candle objects
        """
        try:
            # 1. Check cache first
            start_str = start.isoformat()
            end_str = end.isoformat()
            cached_candles = self.cache.get_cached_market_data(
                symbol=symbol,
                exchange=exchange,
                timeframe=timeframe,
                start=start_str,
                end=end_str,
                max_age_hours=self.cache_max_age_hours
            )
            if cached_candles is not None:
                logger.debug(f"Found {len(cached_candles)} cached candles for {symbol}")
                logger.debug(f"Requested range: {start} to {end}")
                logger.debug(f"Cached range: {cached_candles[0].timestamp} to {cached_candles[-1].timestamp}")
                
                # Check if the cached data fully covers the request
                cache_start = cached_candles[0].timestamp
                cache_end = cached_candles[-1].timestamp
                
                # Make sure timestamps are timezone-naive for comparison
                if cache_start.tzinfo is not None:
                    cache_start = cache_start.replace(tzinfo=None)
                if cache_end.tzinfo is not None:
                    cache_end = cache_end.replace(tzinfo=None)
                
                if cache_start <= start and cache_end >= end:
                    logger.info(f"Using cached data for {symbol} - full coverage available")
                    return cached_candles
                elif self.force_cache_use:
                    logger.info(f"Force cache mode: Using cached data for {symbol} despite incomplete coverage")
                    return cached_candles
                else:
                    logger.info(f"Cache data incomplete for {symbol} - requesting fresh data")
                    logger.debug(f"Coverage check: cache_start ({cache_start}) <= start ({start}): {cache_start <= start}")
                    logger.debug(f"Coverage check: cache_end ({cache_end}) >= end ({end}): {cache_end >= end}")

            all_candles = []
            
            # Convert timeframe to OpenAlgo format
            interval_map = {
                '1m': '1m',
                '5m': '5m', 
                '15m': '15m',
                '30m': '30m',
                '1h': '1h',
                '1d': 'D'
            }
            
            interval = interval_map.get(timeframe, '1h')  # Default to 1 hour
            
            # OpenAlgo historical data call - use correct parameter names
            self._rate_limit()
            
            response = self.client.history(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                start_date=start.strftime('%Y-%m-%d'),
                end_date=end.strftime('%Y-%m-%d')
            )
            
            # The openalgo library returns a pandas DataFrame for history
            if isinstance(response, pd.DataFrame) and not response.empty:
                # The DataFrame columns are expected to be ['date', 'open', 'high', 'low', 'close', 'volume']
                for index, item in response.iterrows():
                    try:
                        # Parse OpenAlgo response format
                        # The timestamp is the index of the DataFrame row
                        timestamp = index.to_pydatetime()
                        # Make the timestamp timezone-naive to allow comparison with start/end dates
                        if timestamp.tzinfo is not None:
                            timestamp = timestamp.replace(tzinfo=None)
                        
                        candle = Candle(
                            timestamp=timestamp,
                            open=float(item['open']),
                            high=float(item['high']),
                            low=float(item['low']),
                            close=float(item['close']),
                            volume=float(item['volume']),
                            symbol=symbol,
                            exchange=exchange
                        )
                        all_candles.append(candle)
                    except (KeyError, ValueError, TypeError) as e:
                        logger.warning(f"Error parsing candle data: {e} - {item}")
                        continue
                # Filter by date range if data was returned
                if start and end and all_candles:
                    all_candles = [c for c in all_candles if start <= c.timestamp <= end]
                
                logger.info(f"Retrieved and parsed {len(all_candles)} candles for {symbol} {timeframe}")
            else:
                # Log the response if it's not a DataFrame or is empty
                if isinstance(response, pd.DataFrame):
                    logger.warning(f"OpenAlgo returned an empty DataFrame for {symbol} from {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}")
                else:
                    logger.error(f"OpenAlgo history request failed: {response}")
            
            # 2. Cache the new data if any was fetched
            if all_candles:
                self.cache.cache_market_data(all_candles, symbol, exchange, timeframe, start_str, end_str)
            
            return all_candles
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return []
    
    def get_quote(self, symbol: str, exchange: str) -> Optional[Quote]:
        """
        Get current quote/price for a symbol using OpenAlgo.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            
        Returns:
            Quote object or None if failed
        """
        try:
            self._rate_limit()
            
            response = self.client.quotes(symbol=symbol, exchange=exchange)
            
            if response.get('status') == 'success':
                data = response.get('data', {})
                
                quote = Quote(
                    symbol=symbol,
                    exchange=exchange,
                    timestamp=datetime.now(),
                    bid=data.get('bid'),
                    ask=data.get('ask'),
                    last=float(data.get('ltp', 0)),
                    volume=data.get('volume')
                )
                
                return quote
            else:
                logger.error(f"OpenAlgo quotes request failed: {response}")
                return None
            
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None
    
    def get_symbols(self, exchange: str) -> List[Dict[str, Any]]:
        """
        Get available symbols for an exchange using OpenAlgo.
        
        Args:
            exchange: Exchange name
            
        Returns:
            List of symbol information
        """
        try:
            self._rate_limit()
            
            # OpenAlgo might have a symbols endpoint
            # This is a placeholder - adapt based on actual OpenAlgo API
            response = self.client.searchscrip(exchange=exchange)
            
            if response.get('status') == 'success':
                symbols = response.get('data', [])
                logger.info(f"Retrieved {len(symbols)} symbols for {exchange}")
                return symbols
            else:
                logger.error(f"OpenAlgo symbols request failed: {response}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching symbols for {exchange}: {e}")
            # Return common NSE symbols as fallback
            if exchange.upper() == 'NSE':
                return [
                    {'symbol': 'RELIANCE', 'exchange': 'NSE'},
                    {'symbol': 'TCS', 'exchange': 'NSE'},
                    {'symbol': 'INFY', 'exchange': 'NSE'},
                    {'symbol': 'HDFCBANK', 'exchange': 'NSE'},
                    {'symbol': 'ICICIBANK', 'exchange': 'NSE'}
                ]
            return []
    
    def get_exchanges(self) -> List[str]:
        """
        Get list of available exchanges.
        
        Returns:
            List of exchange names
        """
        # OpenAlgo typically supports these exchanges
        return ['NSE', 'BSE', 'MCX', 'NCDEX']
    
    def test_connection(self) -> bool:
        """
        Test connection to OpenAlgo API.
        
        Returns:
            True if connection successful
        """
        try:
            # Test with a simple quote request
            response = self.client.quotes(symbol='RELIANCE', exchange='NSE')
            return response.get('status') == 'success'
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    @classmethod
    def create_from_config(cls, config_dict: Dict[str, Any]) -> 'OpenAlgoDataProvider':
        """
        Create provider from configuration dictionary.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            OpenAlgoDataProvider instance
        """
        config = OpenAlgoConfig(**config_dict)
        return cls(config)
