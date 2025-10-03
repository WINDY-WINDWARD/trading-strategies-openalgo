# app/core/metrics.py
"""
Performance metrics calculator for backtesting results.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging
from ..models.results import PerformanceMetrics, Trade, EquityPoint


logger = logging.getLogger(__name__)


class MetricsCalculator:
    """
    Calculate comprehensive performance metrics for backtest results.
    
    Includes traditional metrics like Sharpe ratio, maximum drawdown,
    and trading-specific metrics like win rate and profit factor.
    """
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize metrics calculator.
        
        Args:
            risk_free_rate: Annual risk-free rate for Sharpe calculation
        """
        self.risk_free_rate = risk_free_rate
        logger.debug(f"Metrics calculator initialized with risk-free rate: {risk_free_rate:.2%}")
    
    def calculate_metrics(
        self,
        initial_capital: float,
        final_capital: float,
        equity_curve: List[EquityPoint],
        trades: List[Trade],
        start_date: datetime,
        end_date: datetime,
        delivery_trades_count: int = 0,
        intraday_trades_count: int = 0,
        total_delivery_tax: float = 0.0,
        total_intraday_tax: float = 0.0,
        total_tax_payable: float = 0.0
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics.
        
        Args:
            initial_capital: Starting capital
            final_capital: Final capital
            equity_curve: List of equity curve points
            trades: List of completed trades
            start_date: Backtest start date
            end_date: Backtest end date
            
        Returns:
            PerformanceMetrics object
        """
        if not equity_curve or not trades:
            # Return basic metrics if no data
            return self._create_empty_metrics(initial_capital)
        
        # Basic return calculations
        total_return = final_capital - initial_capital
        total_return_pct = (total_return / initial_capital) * 100
        
        # Time period calculations
        duration_days = (end_date - start_date).days
        duration_years = duration_days / 365.25
        
        # Annualized return
        if duration_years > 0:
            annualized_return = ((final_capital / initial_capital) ** (1 / duration_years) - 1) * 100
        else:
            annualized_return = 0.0
        
        # Drawdown calculations
        max_drawdown, max_drawdown_pct = self._calculate_max_drawdown(equity_curve)
        
        # Risk metrics
        volatility = self._calculate_volatility(equity_curve, duration_years)
        sharpe_ratio = self._calculate_sharpe_ratio(annualized_return, volatility)
        sortino_ratio = self._calculate_sortino_ratio(equity_curve, annualized_return)
        calmar_ratio = self._calculate_calmar_ratio(annualized_return, max_drawdown_pct)
        
        # Trading metrics
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.pnl > 0])
        losing_trades = len([t for t in trades if t.pnl < 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        # Debug: Log trade details
        logger.info(f"Total trades: {total_trades}")
        if total_trades > 0:
            pnl_values = [t.pnl for t in trades[:10]]  # First 10 trades
            logger.info(f"First 10 trade PnL values: {pnl_values}")
            logger.info(f"Trades with pnl > 0: {winning_trades}, Trades with pnl < 0: {losing_trades}")
        
        # P&L metrics
        total_fees = sum(t.fees for t in trades)
        peak_capital = max(point.equity for point in equity_curve)
        
        # Average trade metrics
        avg_trade_pnl = float(np.mean([t.pnl for t in trades])) if trades else 0.0
        winning_pnl = [t.pnl for t in trades if t.pnl > 0]
        losing_pnl = [t.pnl for t in trades if t.pnl < 0]
        
        avg_win_pnl = float(np.mean(winning_pnl)) if winning_pnl else 0.0
        avg_loss_pnl = float(np.mean(losing_pnl)) if losing_pnl else 0.0
        
        # Profit factor
        gross_profit = sum(winning_pnl) if winning_pnl else 0
        gross_loss = abs(sum(losing_pnl)) if losing_pnl else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
        
        # Trade duration
        avg_trade_duration = float(np.mean([t.duration_hours for t in trades])) if trades else 0.0
        
        # Consecutive wins/losses
        max_consecutive_wins, max_consecutive_losses = self._calculate_consecutive_trades(trades)
        
        # Largest win/loss
        largest_win = float(max([t.pnl for t in trades], default=0))
        largest_loss = float(min([t.pnl for t in trades], default=0))
        
        # Debug logging
        logger.info(f"Metrics calculated - Winning trades: {winning_trades}, Losing trades: {losing_trades}")
        logger.info(f"Metrics calculated - Max consecutive wins: {max_consecutive_wins}, Max consecutive losses: {max_consecutive_losses}")
        logger.info(f"Metrics calculated - Largest win: {largest_win}, Largest loss: {largest_loss}")
        
        return PerformanceMetrics(
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            volatility=volatility,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_trade_pnl=avg_trade_pnl,
            avg_win_pnl=avg_win_pnl,
            avg_loss_pnl=avg_loss_pnl,
            avg_trade_duration=avg_trade_duration,
            initial_capital=initial_capital,
            final_capital=final_capital,
            peak_capital=peak_capital,
            total_fees=total_fees,
            delivery_trades_count=delivery_trades_count,
            intraday_trades_count=intraday_trades_count,
            total_delivery_tax=total_delivery_tax,
            total_intraday_tax=total_intraday_tax,
            total_tax_payable=total_tax_payable,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
            largest_win=largest_win,
            largest_loss=largest_loss
        )
    
    def _calculate_max_drawdown(
        self, 
        equity_curve: List[EquityPoint]
    ) -> Tuple[float, float]:
        """
        Calculate maximum drawdown in absolute and percentage terms.
        
        Args:
            equity_curve: List of equity points
            
        Returns:
            Tuple of (max_drawdown_abs, max_drawdown_pct)
        """
        if not equity_curve:
            return 0.0, 0.0
        
        peak = equity_curve[0].equity
        max_drawdown_abs = 0.0
        max_drawdown_pct = 0.0
        
        for point in equity_curve:
            if point.equity > peak:
                peak = point.equity
            
            drawdown_abs = peak - point.equity
            drawdown_pct = (drawdown_abs / peak * 100) if peak > 0 else 0
            
            if drawdown_abs > max_drawdown_abs:
                max_drawdown_abs = drawdown_abs
            if drawdown_pct > max_drawdown_pct:
                max_drawdown_pct = drawdown_pct
        
        return max_drawdown_abs, max_drawdown_pct
    
    def _calculate_volatility(
        self,
        equity_curve: List[EquityPoint],
        duration_years: float
    ) -> float:
        """
        Calculate annualized volatility of returns.
        
        Args:
            equity_curve: List of equity points
            duration_years: Duration in years
            
        Returns:
            Annualized volatility as percentage
        """
        if len(equity_curve) < 2:
            return 0.0
        
        # Calculate daily returns
        returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i-1].equity
            curr_equity = equity_curve[i].equity
            
            if prev_equity > 0:
                daily_return = (curr_equity - prev_equity) / prev_equity
                returns.append(daily_return)
        
        if not returns:
            return 0.0
        
        # Calculate annualized volatility
        daily_vol = np.std(returns, ddof=1)
        
        # Annualize assuming 252 trading days per year
        annualized_vol = float(daily_vol * np.sqrt(252) * 100)
        
        return annualized_vol
    
    def _calculate_sharpe_ratio(
        self,
        annualized_return: float,
        volatility: float
    ) -> Optional[float]:
        """
        Calculate Sharpe ratio.
        
        Args:
            annualized_return: Annualized return percentage
            volatility: Annualized volatility percentage
            
        Returns:
            Sharpe ratio or None if cannot calculate
        """
        if volatility <= 0:
            return None
        
        excess_return = annualized_return - (self.risk_free_rate * 100)
        return excess_return / volatility
    
    def _calculate_sortino_ratio(
        self,
        equity_curve: List[EquityPoint],
        annualized_return: float
    ) -> Optional[float]:
        """
        Calculate Sortino ratio (using downside deviation).
        
        Args:
            equity_curve: List of equity points
            annualized_return: Annualized return percentage
            
        Returns:
            Sortino ratio or None if cannot calculate
        """
        if len(equity_curve) < 2:
            return None
        
        # Calculate daily returns
        returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i-1].equity
            curr_equity = equity_curve[i].equity
            
            if prev_equity > 0:
                daily_return = (curr_equity - prev_equity) / prev_equity
                returns.append(daily_return)
        
        if not returns:
            return None
        
        # Calculate downside deviation
        target_return = self.risk_free_rate / 252  # Daily risk-free rate
        downside_returns = [min(0, r - target_return) for r in returns]
        downside_deviation = np.std(downside_returns, ddof=1) if downside_returns else 0
        
        if downside_deviation <= 0:
            return None
        
        # Annualize
        annual_downside_dev = downside_deviation * np.sqrt(252) * 100
        excess_return = annualized_return - (self.risk_free_rate * 100)
        
        return excess_return / annual_downside_dev
    
    def _calculate_calmar_ratio(
        self,
        annualized_return: float,
        max_drawdown_pct: float
    ) -> Optional[float]:
        """
        Calculate Calmar ratio (return / max drawdown).
        
        Args:
            annualized_return: Annualized return percentage
            max_drawdown_pct: Maximum drawdown percentage
            
        Returns:
            Calmar ratio or None if cannot calculate
        """
        if max_drawdown_pct <= 0:
            return None
        
        return annualized_return / max_drawdown_pct
    
    def _calculate_consecutive_trades(
        self,
        trades: List[Trade]
    ) -> Tuple[int, int]:
        """
        Calculate maximum consecutive wins and losses.
        
        Args:
            trades: List of trades
            
        Returns:
            Tuple of (max_consecutive_wins, max_consecutive_losses)
        """
        if not trades:
            return 0, 0
        
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        
        for trade in trades:
            if trade.pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif trade.pnl < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
            else:
                # Breakeven trade
                current_wins = 0
                current_losses = 0
        
        return max_wins, max_losses
    
    def _create_empty_metrics(self, initial_capital: float) -> PerformanceMetrics:
        """
        Create empty metrics for cases with no trades.
        
        Args:
            initial_capital: Initial capital amount
            
        Returns:
            PerformanceMetrics with zero values
        """
        return PerformanceMetrics(
            total_return=0.0,
            total_return_pct=0.0,
            annualized_return=0.0,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=None,
            sortino_ratio=None,
            calmar_ratio=None,
            volatility=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            profit_factor=None,
            avg_trade_pnl=0.0,
            avg_win_pnl=0.0,
            avg_loss_pnl=0.0,
            avg_trade_duration=0.0,
            initial_capital=initial_capital,
            final_capital=initial_capital,
            peak_capital=initial_capital,
            total_fees=0.0,
            max_consecutive_wins=0,
            max_consecutive_losses=0,
            largest_win=0.0,
            largest_loss=0.0
        )
    
    def calculate_rolling_metrics(
        self,
        equity_curve: List[EquityPoint],
        window_days: int = 30
    ) -> List[Dict]:
        """
        Calculate rolling performance metrics.
        
        Args:
            equity_curve: List of equity points
            window_days: Rolling window size in days
            
        Returns:
            List of rolling metrics dictionaries
        """
        if len(equity_curve) < window_days:
            return []
        
        rolling_metrics = []
        
        for i in range(window_days, len(equity_curve)):
            window_data = equity_curve[i-window_days:i+1]
            
            if len(window_data) < 2:
                continue
            
            # Calculate metrics for this window
            start_equity = window_data[0].equity
            end_equity = window_data[-1].equity
            
            window_return = (end_equity - start_equity) / start_equity * 100
            
            # Rolling volatility
            returns = []
            for j in range(1, len(window_data)):
                prev_equity = window_data[j-1].equity
                curr_equity = window_data[j].equity
                if prev_equity > 0:
                    returns.append((curr_equity - prev_equity) / prev_equity)
            
            window_vol = np.std(returns, ddof=1) * np.sqrt(252) * 100 if returns else 0
            
            # Rolling max drawdown
            window_max_dd, window_max_dd_pct = self._calculate_max_drawdown(window_data)
            
            rolling_metrics.append({
                'timestamp': window_data[-1].timestamp,
                'window_return': window_return,
                'window_volatility': window_vol,
                'window_max_drawdown': window_max_dd,
                'window_max_drawdown_pct': window_max_dd_pct,
                'window_sharpe': (window_return - self.risk_free_rate * 100) / window_vol if window_vol > 0 else None
            })
        
        return rolling_metrics
