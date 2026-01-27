# app/data/synthetic_data.py
"""
Synthetic data generator for testing and fallback.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional
import random
from ..models.market_data import Candle
from ..utils.time_helpers import timeframe_to_seconds, generate_time_range


class SyntheticDataProvider:
    """
    Generates synthetic OHLCV data for backtesting.
    
    This provider creates realistic market data using various models
    including geometric Brownian motion, mean reversion, and trending patterns.
    """
    
    def __init__(self, seed: Optional[int] = None):
        """
        Initialize synthetic data provider.
        
        Args:
            seed: Random seed for reproducible data generation
        """
        self.seed = seed
        if seed is not None:
            np.random.seed(seed)
            random.seed(seed)
    
    def generate_ohlcv(
        self,
        symbol: str,
        exchange: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1h",
        initial_price: float = 2500.0,
        volatility: float = 0.02,
        trend: float = 0.0001,
        volume_base: float = 100000
    ) -> List[Candle]:
        """
        Generate synthetic OHLCV data.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            start: Start datetime
            end: End datetime
            timeframe: Timeframe string
            initial_price: Starting price
            volatility: Price volatility (daily)
            trend: Daily drift/trend
            volume_base: Base volume for generation
            
        Returns:
            List of Candle objects
        """
        # Generate time index
        time_index = generate_time_range(start, end, timeframe)
        
        if len(time_index) == 0:
            return []
        
        # Calculate timeframe adjustment for volatility
        timeframe_seconds = timeframe_to_seconds(timeframe)
        timeframe_days = timeframe_seconds / 86400
        adjusted_volatility = volatility * np.sqrt(timeframe_days)
        adjusted_trend = trend * timeframe_days
        
        # Generate price series using geometric Brownian motion
        n_periods = len(time_index)
        returns = np.random.normal(
            adjusted_trend, 
            adjusted_volatility, 
            n_periods
        )
        
        # Add some autocorrelation for realism
        returns = self._add_autocorrelation(returns, 0.1)
        
        # Calculate cumulative prices
        log_returns = np.cumsum(returns)
        prices = initial_price * np.exp(log_returns)
        
        # Generate OHLC from prices
        candles = []
        
        for i, timestamp in enumerate(time_index):
            if i == 0:
                open_price = initial_price
            else:
                open_price = candles[i-1].close
            
            # Generate intrabar movement
            close_price = prices[i]
            
            # Add some intrabar volatility
            intrabar_range = abs(close_price - open_price) * 0.5 + open_price * adjusted_volatility * np.random.random()
            
            high_price = max(open_price, close_price) + intrabar_range * np.random.random()
            low_price = min(open_price, close_price) - intrabar_range * np.random.random()
            
            # Ensure price constraints
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)
            
            # Generate volume with some randomness
            volume = volume_base * (0.5 + np.random.random()) * (1 + abs(returns[i]) * 10)
            
            candle = Candle(
                timestamp=timestamp,
                open=float(round(open_price, 2)),
                high=float(round(high_price, 2)),
                low=float(round(low_price, 2)),
                close=float(round(close_price, 2)),
                volume=int(round(volume)),
                symbol=symbol,
                exchange=exchange
            )
            
            candles.append(candle)
        
        return candles
    
    def generate_trending_data(
        self,
        symbol: str,
        exchange: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1h",
        initial_price: float = 2500.0,
        trend_strength: float = 0.001,
        volatility: float = 0.015
    ) -> List[Candle]:
        """
        Generate synthetic data with a clear trend.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            start: Start datetime
            end: End datetime
            timeframe: Timeframe string
            initial_price: Starting price
            trend_strength: Strength of trend (daily)
            volatility: Price volatility
            
        Returns:
            List of trending Candle objects
        """
        return self.generate_ohlcv(
            symbol=symbol,
            exchange=exchange,
            start=start,
            end=end,
            timeframe=timeframe,
            initial_price=initial_price,
            volatility=volatility,
            trend=trend_strength
        )
    
    def generate_sideways_data(
        self,
        symbol: str,
        exchange: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1h",
        initial_price: float = 2500.0,
        range_pct: float = 0.1,
        volatility: float = 0.01
    ) -> List[Candle]:
        """
        Generate synthetic sideways/ranging market data.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            start: Start datetime
            end: End datetime
            timeframe: Timeframe string
            initial_price: Starting price
            range_pct: Price range as percentage of initial price
            volatility: Price volatility
            
        Returns:
            List of ranging Candle objects
        """
        time_index = generate_time_range(start, end, timeframe)
        
        if len(time_index) == 0:
            return []
        
        # Create mean-reverting price series
        n_periods = len(time_index)
        center_price = initial_price
        max_price = center_price * (1 + range_pct / 2)
        min_price = center_price * (1 - range_pct / 2)
        
        # Generate mean-reverting series
        prices = [initial_price]
        
        for i in range(1, n_periods):
            current_price = prices[-1]
            
            # Mean reversion force
            mean_reversion = (center_price - current_price) / center_price * 0.1
            
            # Random component
            random_change = np.random.normal(0, volatility)
            
            # Combine forces
            price_change = mean_reversion + random_change
            new_price = current_price * (1 + price_change)
            
            # Keep within range
            new_price = max(min_price, min(max_price, new_price))
            prices.append(new_price)
        
        # Convert to OHLC
        candles = []
        
        for i, timestamp in enumerate(time_index):
            if i == 0:
                open_price = initial_price
            else:
                open_price = candles[i-1].close
            
            close_price = prices[i]
            
            # Generate OHLC with some randomness
            price_range = abs(close_price - open_price) * 0.5
            high_offset = price_range * np.random.random() * 0.5
            low_offset = price_range * np.random.random() * 0.5
            
            high_price = max(open_price, close_price) + high_offset
            low_price = min(open_price, close_price) - low_offset
            
            # Volume varies with price movement
            volume = 50000 + abs(close_price - open_price) / open_price * 500000
            
            candle = Candle(
                timestamp=timestamp,
                open=round(open_price, 2),
                high=round(high_price, 2),
                low=round(low_price, 2),
                close=round(close_price, 2),
                volume=round(volume),
                symbol=symbol,
                exchange=exchange
            )
            
            candles.append(candle)
        
        return candles
    
    def generate_volatile_data(
        self,
        symbol: str,
        exchange: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1h",
        initial_price: float = 2500.0,
        base_volatility: float = 0.03,
        volatility_clusters: bool = True
    ) -> List[Candle]:
        """
        Generate highly volatile synthetic data.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            start: Start datetime
            end: End datetime
            timeframe: Timeframe string
            initial_price: Starting price
            base_volatility: Base volatility level
            volatility_clusters: Whether to include volatility clustering
            
        Returns:
            List of volatile Candle objects
        """
        time_index = generate_time_range(start, end, timeframe)
        
        if len(time_index) == 0:
            return []
        
        n_periods = len(time_index)
        
        # Generate volatility series with clustering if enabled
        if volatility_clusters:
            volatilities = self._generate_volatility_clusters(n_periods, base_volatility)
        else:
            volatilities = [base_volatility] * n_periods
        
        # Generate returns with varying volatility
        returns = []
        for vol in volatilities:
            returns.append(np.random.normal(0, vol))
        
        # Calculate prices
        log_returns = np.cumsum(returns)
        prices = initial_price * np.exp(log_returns)
        
        # Convert to OHLC
        candles = []
        
        for i, timestamp in enumerate(time_index):
            if i == 0:
                open_price = initial_price
            else:
                open_price = candles[i-1].close
            
            close_price = prices[i]
            
            # Generate wider OHLC ranges due to volatility
            vol_multiplier = volatilities[i] / base_volatility
            intrabar_range = abs(close_price - open_price) * vol_multiplier
            
            high_price = max(open_price, close_price) + intrabar_range * np.random.random()
            low_price = min(open_price, close_price) - intrabar_range * np.random.random()
            
            # Higher volume during volatile periods
            volume = 100000 * (1 + vol_multiplier * 2) * (0.5 + np.random.random())
            
            candle = Candle(
                timestamp=timestamp,
                open=round(open_price, 2),
                high=round(high_price, 2),
                low=round(low_price, 2),
                close=round(close_price, 2),
                volume=round(volume),
                symbol=symbol,
                exchange=exchange
            )
            
            candles.append(candle)
        
        return candles
    
    def _add_autocorrelation(self, series: np.ndarray, correlation: float) -> np.ndarray:
        """Add autocorrelation to a time series."""
        if correlation == 0:
            return series
        
        result = np.copy(series)
        for i in range(1, len(result)):
            result[i] += correlation * result[i-1]
        
        return result
    
    def _generate_volatility_clusters(self, n_periods: int, base_vol: float) -> List[float]:
        """Generate volatility with clustering (GARCH-like behavior)."""
        volatilities = [base_vol]
        
        for i in range(1, n_periods):
            # Simple volatility clustering model
            prev_vol = volatilities[-1]
            
            # Mean reversion to base volatility
            mean_reversion = 0.1 * (base_vol - prev_vol)
            
            # Shock component
            shock = 0.3 * np.random.normal(0, 0.1 * base_vol)
            
            # Persistence
            persistence = 0.6 * (prev_vol - base_vol)
            
            new_vol = base_vol + mean_reversion + shock + persistence
            
            # Keep volatility positive and reasonable
            new_vol = max(0.001, min(new_vol, base_vol * 5))
            
            volatilities.append(new_vol)
        
        return volatilities
    
    def get_sample_symbols(self) -> List[dict]:
        """
        Get sample symbol configurations for testing.
        
        Returns:
            List of symbol configuration dictionaries
        """
        return [
            {
                "symbol": "RELIANCE",
                "exchange": "NSE", 
                "initial_price": 2500.0,
                "volatility": 0.02,
                "description": "Reliance Industries - Large Cap Stock"
            },
            {
                "symbol": "TATASTEEL", 
                "exchange": "NSE",
                "initial_price": 1200.0,
                "volatility": 0.035,
                "description": "Tata Steel - Cyclical Stock"
            },
            {
                "symbol": "INFY",
                "exchange": "NSE",
                "initial_price": 1800.0,
                "volatility": 0.025,
                "description": "Infosys - IT Stock"
            },
            {
                "symbol": "BANKNIFTY",
                "exchange": "NSE",
                "initial_price": 45000.0,
                "volatility": 0.04,
                "description": "Bank Nifty Index - High Volatility"
            }
        ]
