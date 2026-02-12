# app/models/config.py
"""
Configuration models for the backtesting engine.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, validator
from datetime import datetime, date


class OpenAlgoConfig(BaseModel):
    """OpenAlgo API configuration."""
    api_key: str = Field(..., description="OpenAlgo API key")
    base_url: str = Field(default="http://127.0.0.1:8800", description="OpenAlgo base URL")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    retry_attempts: int = Field(default=3, description="Number of retry attempts")
    # Cache configuration
    force_cache_use: bool = Field(default=False, description="Force use of cached data even if incomplete")
    cache_max_age_hours: int = Field(default=24, description="Maximum cache age in hours")


class DataConfig(BaseModel):
    """Data source configuration."""
    exchange: str = Field(default="NSE", description="Exchange name")
    symbol: str = Field(default="RELIANCE", description="Trading symbol")
    timeframe: str = Field(default="1h", description="Data timeframe")
    start: str = Field(..., description="Start date (YYYY-MM-DD)")
    end: str = Field(..., description="End date (YYYY-MM-DD)")
    cache_dir: str = Field(default=".cache/data", description="Data cache directory")
    use_synthetic: bool = Field(default=True, description="Use synthetic data fallback")

    @validator('timeframe')
    def validate_timeframe(cls, v):
        valid_timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
        if v not in valid_timeframes:
            raise ValueError(f"Timeframe must be one of {valid_timeframes}")
        return v


class BacktestConfig(BaseModel):
    """Backtest execution configuration."""
    initial_cash: float = Field(default=100000.0, description="Initial cash amount")
    fee_bps: float = Field(default=5.0, description="Transaction fee in basis points")
    slippage_bps: float = Field(default=2.0, description="Slippage in basis points")
    seed: int = Field(default=42, description="Random seed for reproducibility")
    candle_execution: bool = Field(default=True, description="Execute orders at candle close")
    commission_per_trade: float = Field(default=0.0, description="Fixed commission per trade")
    delivery_tax_pct: float = Field(default=0.1, description="Delivery tax percentage")
    intraday_tax_pct: float = Field(default=0.025, description="Intraday tax percentage")


class StrategyConfig(BaseModel):
    """Strategy configuration."""
    type: str = Field(default="grid", description="Strategy type")
    
    # Grid strategy parameters
    grid_levels: int = Field(default=10, description="Number of grid levels")
    grid_spacing_pct: float = Field(default=1.0, description="Grid spacing percentage")
    order_amount: float = Field(default=1000.0, description="Order amount per grid level")
    grid_type: str = Field(default="arithmetic", description="Grid type: arithmetic or geometric")
    auto_reset: bool = Field(default=True, description="Auto reset grid on breakout")
    initial_position_strategy: str = Field(default="wait_for_buy", description="Initial position strategy")
    
    # Common strategy parameters
    stop_loss_pct: float = Field(default=5.0, description="Stop loss percentage")
    take_profit_pct: float = Field(default=10.0, description="Take profit percentage")
    
    # Supertrend strategy parameters
    atr_period: int = Field(default=10, description="ATR period for Supertrend calculation")
    atr_multiplier: float = Field(default=3.0, description="ATR multiplier for Supertrend calculation")
    max_order_amount: float = Field(default=1000.0, description="Maximum amount in rupees per trade for Supertrend strategy")
    
    # Buffer configuration for strategies requiring historical data
    buffer_enabled: bool = Field(default=True, description="Enable data buffer for accurate calculations")
    buffer_days: int = Field(default=90, description="Number of buffer days for historical data")
    buffer_mode: str = Field(default="skip_initial", description="Buffer mode: 'skip_initial' or 'fetch_additional'")

    @validator('grid_type')
    def validate_grid_type(cls, v):
        if v not in ['arithmetic', 'geometric']:
            raise ValueError("Grid type must be 'arithmetic' or 'geometric'")
        return v
    
    @validator('buffer_mode')
    def validate_buffer_mode(cls, v):
        if v not in ['skip_initial', 'fetch_additional']:
            raise ValueError("Buffer mode must be 'skip_initial' or 'fetch_additional'")
        return v
    
    @validator('buffer_days')
    def validate_buffer_days(cls, v):
        if v < 1 or v > 365:
            raise ValueError("Buffer days must be between 1 and 365")
        return v
    
    @validator('type')
    def validate_strategy_type(cls, v):
        if v not in ['grid', 'supertrend']:
            raise ValueError("Strategy type must be 'grid' or 'supertrend'")
        return v


class UIConfig(BaseModel):
    """Web UI configuration."""
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")
    title: str = Field(default="Grid Trading Backtester", description="UI title")


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format")
    file: Optional[str] = Field(default=None, description="Log file path")


class AppConfig(BaseModel):
    """Main application configuration."""
    openalgo: OpenAlgoConfig
    data: DataConfig
    backtest: BacktestConfig
    strategy: StrategyConfig
    ui: UIConfig
    logging: LoggingConfig

    @property
    def run_id(self) -> str:
        """Generate a unique run ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{self.data.symbol}_{self.strategy.type}_{timestamp}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump(mode='python')

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'AppConfig':
        """Create from dictionary."""
        return cls(**config_dict)
