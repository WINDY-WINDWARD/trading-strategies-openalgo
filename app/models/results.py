# app/models/results.py
"""
Backtest results and performance metrics models.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
from .orders import Order


class Trade(BaseModel):
    """Completed trade model."""
    id: str = Field(..., description="Trade ID")
    symbol: str = Field(..., description="Trading symbol")
    entry_time: datetime = Field(..., description="Entry timestamp")
    exit_time: datetime = Field(..., description="Exit timestamp")
    entry_price: float = Field(..., description="Entry price")
    exit_price: float = Field(..., description="Exit price")
    quantity: float = Field(..., description="Trade quantity")
    side: str = Field(..., description="Trade side (LONG/SHORT)")
    pnl: float = Field(..., description="Profit and Loss")
    pnl_pct: float = Field(..., description="P&L percentage")
    fees: float = Field(default=0.0, description="Total fees")
    duration_seconds: float = Field(..., description="Trade duration in seconds")
    
    @property
    def duration_minutes(self) -> float:
        """Trade duration in minutes."""
        return self.duration_seconds / 60
    
    @property
    def duration_hours(self) -> float:
        """Trade duration in hours."""
        return self.duration_seconds / 3600
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'side': self.side,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            'fees': self.fees,
            'duration_seconds': self.duration_seconds
        }


class PerformanceMetrics(BaseModel):
    """Performance metrics for backtest results."""
    
    # Basic metrics
    total_return: float = Field(..., description="Total return")
    total_return_pct: float = Field(..., description="Total return percentage")
    annualized_return: float = Field(..., description="Annualized return")
    max_drawdown: float = Field(..., description="Maximum drawdown")
    max_drawdown_pct: float = Field(..., description="Maximum drawdown percentage")
    
    # Risk metrics
    sharpe_ratio: Optional[float] = Field(None, description="Sharpe ratio")
    sortino_ratio: Optional[float] = Field(None, description="Sortino ratio")
    calmar_ratio: Optional[float] = Field(None, description="Calmar ratio")
    volatility: float = Field(..., description="Portfolio volatility")
    
    # Trading metrics
    total_trades: int = Field(..., description="Total number of trades")
    winning_trades: int = Field(..., description="Number of winning trades")
    losing_trades: int = Field(..., description="Number of losing trades")
    win_rate: float = Field(..., description="Win rate percentage")
    profit_factor: Optional[float] = Field(None, description="Profit factor")
    
    # Average metrics
    avg_trade_pnl: float = Field(..., description="Average trade P&L")
    avg_win_pnl: float = Field(..., description="Average winning trade P&L")
    avg_loss_pnl: float = Field(..., description="Average losing trade P&L")
    avg_trade_duration: float = Field(..., description="Average trade duration in hours")
    
    # Portfolio metrics
    initial_capital: float = Field(..., description="Initial capital")
    final_capital: float = Field(..., description="Final capital")
    peak_capital: float = Field(..., description="Peak capital reached")
    total_fees: float = Field(..., description="Total fees paid")
    
    # Tax metrics
    delivery_trades_count: int = Field(default=0, description="Number of delivery trades")
    intraday_trades_count: int = Field(default=0, description="Number of intraday trades")
    total_delivery_tax: float = Field(default=0.0, description="Total delivery tax paid")
    total_intraday_tax: float = Field(default=0.0, description="Total intraday tax paid")
    total_tax_payable: float = Field(default=0.0, description="Total tax payable")
    
    # Additional metrics
    max_consecutive_wins: int = Field(default=0, description="Maximum consecutive wins")
    max_consecutive_losses: int = Field(default=0, description="Maximum consecutive losses")
    largest_win: float = Field(default=0.0, description="Largest single win")
    largest_loss: float = Field(default=0.0, description="Largest single loss")
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        # Use model_dump for Pydantic v2
        result = self.model_dump(mode='python', exclude_none=False)
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"PerformanceMetrics.to_dict() - winning_trades: {result.get('winning_trades')}, "
                    f"losing_trades: {result.get('losing_trades')}, "
                    f"largest_win: {result.get('largest_win')}, "
                    f"largest_loss: {result.get('largest_loss')}, "
                    f"max_consecutive_wins: {result.get('max_consecutive_wins')}, "
                    f"max_consecutive_losses: {result.get('max_consecutive_losses')}")
        return result


class EquityPoint(BaseModel):
    """Equity curve point."""
    timestamp: datetime = Field(..., description="Timestamp")
    equity: float = Field(..., description="Portfolio equity")
    drawdown: float = Field(..., description="Drawdown from peak")
    drawdown_pct: float = Field(..., description="Drawdown percentage")
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'equity': self.equity,
            'drawdown': self.drawdown,
            'drawdown_pct': self.drawdown_pct
        }


class BacktestResult(BaseModel):
    """Complete backtest results."""
    run_id: str = Field(..., description="Unique run identifier")
    symbol: str = Field(..., description="Trading symbol")
    exchange: str = Field(..., description="Exchange name")
    start_time: datetime = Field(..., description="Backtest start time")
    end_time: datetime = Field(..., description="Backtest end time")
    created_at: datetime = Field(default_factory=datetime.now, description="Result creation time")
    
    # Configuration
    config: Dict[str, Any] = Field(..., description="Backtest configuration")
    
    # Results
    trades: List[Trade] = Field(default_factory=list, description="All completed trades")
    orders: List[Order] = Field(default_factory=list, description="All orders")
    equity_curve: List[EquityPoint] = Field(default_factory=list, description="Equity curve data")
    metrics: PerformanceMetrics = Field(..., description="Performance metrics")
    strategy_state: Optional[Dict[str, Any]] = Field(None, description="Strategy state at end of backtest")
    
    # Metadata
    total_candles: int = Field(..., description="Total number of candles processed")
    execution_time: float = Field(..., description="Backtest execution time in seconds")
    
    @property
    def duration_days(self) -> float:
        """Backtest duration in days."""
        return (self.end_time - self.start_time).total_seconds() / 86400
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'run_id': self.run_id,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'created_at': self.created_at.isoformat(),
            'config': self.config,
            'trades': [trade.to_dict() for trade in self.trades],
            'orders': [order.to_dict() for order in self.orders],
            'equity_curve': [point.to_dict() for point in self.equity_curve],
            'metrics': self.metrics.to_dict(),
            'strategy_state': self.strategy_state,
            'total_candles': self.total_candles,
            'execution_time': self.execution_time
        }
    
    def save_to_json(self, filepath: str) -> None:
        """Save results to JSON file."""
        import json
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def save_to_csv(self, filepath: str) -> None:
        """Save trades to CSV file."""
        import pandas as pd
        if self.trades:
            trades_df = pd.DataFrame([trade.to_dict() for trade in self.trades])
            trades_df.to_csv(filepath, index=False)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
