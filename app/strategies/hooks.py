# app/strategies/hooks.py
"""
Reusable lifecycle hooks for UniversalStrategyAdapter.
Provides common customization patterns without requiring full custom adapters.
"""

import logging
import pandas as pd
from typing import Any, Dict, Callable
from ..models.market_data import Candle

logger = logging.getLogger(__name__)


class StrategyHooks:
    """
    Collection of reusable hooks for common strategy customization needs.
    
    Hooks can be attached to UniversalStrategyAdapter to add custom behavior
    without writing a full adapter class.
    
    Example:
        adapter = UniversalStrategyAdapter(MyBot)
        adapter.setup_hook = StrategyHooks.log_bot_state
        adapter.pre_bar_hook = StrategyHooks.update_indicators
    """
    
    @staticmethod
    def log_bot_state(bot: Any, params: Dict) -> None:
        """
        Setup hook: Log bot initialization state.
        
        Args:
            bot: Trading bot instance
            params: Initialization parameters
        """
        logger.info(f"Bot initialized: {bot.__class__.__name__}")
        logger.info(f"Parameters: {list(params.keys())}")
        
        if hasattr(bot, 'symbol'):
            logger.info(f"Symbol: {bot.symbol}")
        if hasattr(bot, 'exchange'):
            logger.info(f"Exchange: {bot.exchange}")
    
    @staticmethod
    def update_indicators(bot: Any, candle: Candle) -> None:
        """
        Pre-bar hook: Update technical indicators before strategy execution.
        
        Args:
            bot: Trading bot instance
            candle: Current market data candle
        """
        # Example: Update moving averages, RSI, etc.
        if hasattr(bot, 'update_indicators'):
            bot.update_indicators(candle)
    
    @staticmethod
    def log_performance(bot: Any, candle: Candle) -> None:
        """
        Post-bar hook: Log performance metrics after bar processing.
        
        Args:
            bot: Trading bot instance
            candle: Current market data candle
        """
        if hasattr(bot, 'get_performance_summary'):
            perf = bot.get_performance_summary()
            if perf and isinstance(perf, dict):
                logger.debug(f"Performance: PnL={perf.get('total_pnl', 0):.2f}, "
                           f"Trades={perf.get('total_trades', 0)}")
    
    @staticmethod
    def calculate_supertrend(bot: Any, candle: Candle) -> None:
        """
        Pre-bar hook: Calculate Supertrend indicator.
        Specific to strategies using Supertrend.
        
        Args:
            bot: Trading bot instance (must be SupertrendTradingBot)
            candle: Current market data candle
        """
        if hasattr(bot, 'calculate_supertrend') and hasattr(bot, 'ohlc_data'):
            if bot.ohlc_data is not None and not bot.ohlc_data.empty:
                bot.ohlc_data = bot.calculate_supertrend(bot.ohlc_data)
    
    @staticmethod
    def save_state_periodic(interval: int = 100):
        """
        Post-bar hook factory: Save bot state periodically.
        
        Args:
            interval: Save state every N bars
            
        Returns:
            Hook function
        """
        counter = {'count': 0}
        
        def hook(bot: Any, candle: Candle) -> None:
            counter['count'] += 1
            if counter['count'] % interval == 0:
                if hasattr(bot, 'save_state'):
                    try:
                        bot.save_state()
                        logger.debug(f"State saved at bar {counter['count']}")
                    except Exception as e:
                        logger.error(f"Failed to save state: {e}")
        
        return hook
    
    @staticmethod
    def risk_management_check(bot: Any, candle: Candle) -> None:
        """
        Pre-bar hook: Check risk management conditions.
        
        Args:
            bot: Trading bot instance
            candle: Current market data candle
        """
        # Check if bot has risk management methods
        if hasattr(bot, 'check_risk_limits'):
            bot.check_risk_limits()
        
        # Example: Emergency stop on large drawdown
        if hasattr(bot, 'unrealized_pnl'):
            max_drawdown_pct = 10.0  # 10% max drawdown
            if hasattr(bot, 'total_profit'):
                total_value = bot.total_profit + bot.unrealized_pnl
                initial_capital = getattr(bot, 'initial_capital', 100000)
                drawdown_pct = ((initial_capital - total_value) / initial_capital) * 100
                
                if drawdown_pct > max_drawdown_pct:
                    logger.warning(f"Max drawdown exceeded: {drawdown_pct:.2f}%")
                    if hasattr(bot, 'is_active'):
                        bot.is_active = False


class BufferHooks:
    """
    Specialized hooks for strategies using historical data buffers.
    """
    
    @staticmethod
    def update_dataframe_buffer(adapter: Any, bot: Any, candle: Candle) -> None:
        """
        Pre-bar hook: Update bot's DataFrame with current candle.
        Used by strategies that maintain their own DataFrames.
        
        Args:
            adapter: UniversalStrategyAdapter instance
            bot: Trading bot instance
            candle: Current market data candle
        """
        if not hasattr(bot, 'ohlc_data'):
            return
        
        # Initialize DataFrame if needed
        if bot.ohlc_data is None:
            bot.ohlc_data = pd.DataFrame()
        
        # Add current candle
        row = pd.DataFrame([{
            'timestamp': candle.timestamp,
            'open': candle.open,
            'high': candle.high,
            'low': candle.low,
            'close': candle.close,
            'volume': candle.volume
        }])
        
        bot.ohlc_data = pd.concat([bot.ohlc_data, row], ignore_index=True)
    
    @staticmethod
    def create_buffer_ready_callback(callback: Callable) -> Callable:
        """
        First-bar hook factory: Execute callback when buffer is ready.
        
        Args:
            callback: Function to call when buffer is ready
            
        Returns:
            Hook function
        """
        def hook(bot: Any, candle: Candle) -> None:
            # This will be called on first bar after buffer is ready
            logger.info("Buffer ready, executing callback")
            callback(bot, candle)
        
        return hook


class OrderHooks:
    """
    Hooks for order management and execution.
    """
    
    @staticmethod
    def log_orders(bot: Any, candle: Candle) -> None:
        """
        Post-bar hook: Log active orders.
        
        Args:
            bot: Trading bot instance
            candle: Current market data candle
        """
        if hasattr(bot, 'pending_orders') and bot.pending_orders:
            logger.debug(f"Active orders: {len(bot.pending_orders)}")
            for order_id, order in bot.pending_orders.items():
                logger.debug(f"  {order_id}: {order.get('action')} @ {order.get('price')}")
    
    @staticmethod
    def cancel_stale_orders(max_age_bars: int = 50):
        """
        Post-bar hook factory: Cancel orders older than N bars.
        
        Args:
            max_age_bars: Maximum age in bars before cancellation
            
        Returns:
            Hook function
        """
        order_ages = {}
        
        def hook(bot: Any, candle: Candle) -> None:
            if not hasattr(bot, 'pending_orders'):
                return
            
            # Age all orders
            for order_id in list(order_ages.keys()):
                order_ages[order_id] += 1
            
            # Add new orders
            for order_id in bot.pending_orders.keys():
                if order_id not in order_ages:
                    order_ages[order_id] = 0
            
            # Cancel stale orders
            for order_id, age in list(order_ages.items()):
                if age > max_age_bars:
                    if hasattr(bot, 'cancel_order'):
                        try:
                            bot.cancel_order(order_id)
                            logger.info(f"Cancelled stale order {order_id} (age: {age} bars)")
                            del order_ages[order_id]
                        except Exception as e:
                            logger.error(f"Failed to cancel order {order_id}: {e}")
        
        return hook


# Convenience function to create hook chains
def chain_hooks(*hooks: Callable) -> Callable:
    """
    Chain multiple hooks together to run sequentially.
    
    Args:
        *hooks: Variable number of hook functions
        
    Returns:
        Combined hook function
    
    Example:
        combined = chain_hooks(
            StrategyHooks.update_indicators,
            StrategyHooks.risk_management_check
        )
        adapter.pre_bar_hook = combined
    """
    def chained_hook(*args, **kwargs):
        for hook in hooks:
            try:
                hook(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in hook {hook.__name__}: {e}", exc_info=True)
    
    return chained_hook
