# app/data/cache_manager.py
"""
Data caching and persistence manager.
"""

import os
from pathlib import Path
from typing import List, Optional, Any, Dict
import sqlite3
from datetime import datetime, timedelta
import hashlib
import logging
from ..models.market_data import Candle


logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages caching of market data and backtest results.
    - Uses SQLite for market data to handle large datasets efficiently.
    """
    
    def __init__(self, cache_dir: str = ".cache", db_name: str = "market_data.db"):
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Base cache directory
            db_name: SQLite database file name
        """
        self.cache_path = Path(cache_dir) / db_name
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.cache_path, detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info(f"Cache manager initialized with SQLite DB at: {self.cache_path}")

    def _create_tables(self):
        """Create database tables if they don't exist."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    PRIMARY KEY (symbol, exchange, timeframe, timestamp)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    request_key TEXT PRIMARY KEY,
                    cached_at TIMESTAMP NOT NULL
                )
            """)

    def _generate_cache_key(self, **kwargs) -> str:
        """
        Generate cache key from parameters.
        
        Args:
            **kwargs: Parameters to include in key
            
        Returns:
            MD5 hash of parameters
        """
        # Sort parameters for consistent key generation
        sorted_params = sorted(kwargs.items())
        key_string = str(sorted_params)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def cache_market_data(
        self,
        candles: List[Candle],
        symbol: str,
        exchange: str,
        timeframe: str,
        start: str,
        end: str,
        source: str = "unknown"
    ) -> bool:
        """
        Cache market data to disk.
        
        Args:
            candles: List of candle data
            symbol: Trading symbol
            exchange: Exchange name
            timeframe: Timeframe string
            start: Start date string
            end: End date string
            source: Data source name
            
        Returns:
            True if caching successful
        """
        try:
            if not candles:
                logger.warning("No candles to cache")
                return False
            
            # Prepare data for bulk insert
            candle_data = [
                (c.symbol, c.exchange, timeframe, c.timestamp, c.open, c.high, c.low, c.close, c.volume)
                for c in candles
            ]
            
            with self.conn:
                # Insert candle data, ignoring duplicates
                self.conn.executemany("""
                    INSERT OR IGNORE INTO candles (symbol, exchange, timeframe, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, candle_data)
                
                # Record the request
                request_key = self._generate_cache_key(symbol=symbol, exchange=exchange, timeframe=timeframe, start=start, end=end)
                self.conn.execute("""
                    INSERT OR REPLACE INTO requests (request_key, cached_at)
                    VALUES (?, ?)
                """, (request_key, datetime.now()))
            
            logger.info(f"Cached {len(candles)} candles for {symbol} in SQLite DB.")
            return True
            
        except Exception as e:
            logger.error(f"Error caching market data to SQLite: {e}", exc_info=True)
            return False
    
    def get_cached_market_data(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        start: str,
        end: str,
        max_age_hours: int = 24
    ) -> Optional[List[Candle]]:
        """
        Retrieve cached market data.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            timeframe: Timeframe string
            start: Start date string
            end: End date string
            max_age_hours: Maximum cache age in hours
            
        Returns:
            List of cached candles or None if not found/expired
        """
        try:
            request_key = self._generate_cache_key(symbol=symbol, exchange=exchange, timeframe=timeframe, start=start, end=end)
            cursor = self.conn.cursor()
            
            # Check if this exact request was cached recently
            cursor.execute("SELECT cached_at FROM requests WHERE request_key = ?", (request_key,))
            result = cursor.fetchone()
            
            if not result:
                logger.debug(f"No direct cache hit for request key: {request_key}")
                return None

            # Check cache age
            cached_at = result['cached_at']
            age_hours = (datetime.now() - cached_at).total_seconds() / 3600
            
            if age_hours > max_age_hours:
                logger.info(f"Cache expired for {symbol} {timeframe} (age: {age_hours:.1f}h > {max_age_hours}h)")
                return None
            
            logger.debug(f"Cache is fresh for {symbol} {timeframe} (age: {age_hours:.1f}h)")
            
            # Query the data from the database
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            
            cursor.execute("""
                SELECT * FROM candles
                WHERE symbol = ? AND exchange = ? AND timeframe = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """, (symbol, exchange, timeframe, start_dt, end_dt))
            
            rows = cursor.fetchall()
            
            if not rows:
                logger.debug(f"No candles found in cache for {symbol} between {start_dt} and {end_dt}")
                return None

            candles = []
            for row in rows:
                candles.append(Candle(**dict(row)))
            
            logger.info(f"Retrieved {len(candles)} cached candles for {symbol} from SQLite DB.")
            logger.debug(f"Cache date range: {candles[0].timestamp} to {candles[-1].timestamp}")
            return candles
            
        except Exception as e:
            logger.error(f"Error retrieving cached market data from SQLite: {e}", exc_info=True)
            return None
    
    def cache_backtest_result(self, result: Any, run_id: str) -> bool:
        """
        Cache backtest result.
        
        Args:
            result: Backtest result object
            run_id: Unique run identifier
            
        Returns:
            True if caching successful
        """
        try:
            # This part can be extended to save results to DB as well
            # For now, we keep it simple for demonstration
            logger.warning("Backtest result caching to DB is not yet implemented.")
            return True
            
        except Exception as e:
            logger.error(f"Error caching backtest result: {e}")
            return False
    
    def get_cached_backtest_result(self, run_id: str) -> Optional[Any]:
        """
        Retrieve cached backtest result.
        
        Args:
            run_id: Run identifier
            format: Return format ('object' for full object, 'dict' for dictionary)
            
        Returns:
            Cached result or None if not found
        """
        try:
            logger.warning("Getting cached backtest results from DB is not yet implemented.")
            return None
        except Exception as e:
            logger.error(f"Error retrieving cached result: {e}")
            return None
    
    def list_cached_data(self) -> List[Dict[str, Any]]:
        """
        List all cached market data.
        
        Returns:
            List of cache metadata dictionaries
        """
        cached_data = []
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT request_key, cached_at FROM requests ORDER BY cached_at DESC")
            for row in cursor.fetchall():
                cached_data.append(dict(row))
        except Exception as e:
            logger.error(f"Error listing cached data: {e}")
        
        return cached_data
    
    def list_cached_results(self) -> List[str]:
        """
        List all cached backtest results.
        
        Returns:
            List of run IDs
        """
        try:
            logger.warning("Listing cached results from DB is not yet implemented.")
            return []
        except Exception as e:
            logger.error(f"Error listing cached results: {e}")
            return []
    
    def clear_cache(self, older_than_days: int = 7) -> int:
        """
        Clear old cache files.
        
        Args:
            older_than_days: Remove files older than this many days
            
        Returns:
            Number of files removed
        """
        cutoff_time = datetime.now() - timedelta(days=older_than_days)
        files_removed = 0
        
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute("DELETE FROM requests WHERE cached_at < ?", (cutoff_time,))
                files_removed = cursor.rowcount
                # Note: This doesn't remove the candle data itself, just the request record.
                # A more complex VACUUM or cleanup process could be added.
            
            logger.info(f"Cleared {files_removed} old cache files")
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
        
        return files_removed
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            stats = {
                'db_size_mb': round(self.cache_path.stat().st_size / (1024 * 1024), 2),
                'total_candles': 0,
                'total_requests': 0
            }
            cursor = self.conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM candles")
            stats['total_candles'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM requests")
            stats['total_requests'] = cursor.fetchone()[0]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    def __del__(self):
        """Close the database connection on object destruction."""
        if self.conn:
            self.conn.close()
