# app/strategies/universal_strategy_adapter.py
"""
Universal adapter to wrap any TradingBot for use in the backtesting engine.
Handles 80% of strategy adaptation with zero custom code.
"""

import logging
import inspect
import pandas as pd
from typing import Any, Dict, List, Optional, Type, Callable
from datetime import datetime

from strats.trading_bot import TradingBot
from .base_strategy import BaseStrategy
from .util.mock_openalgo_client import MockOpenAlgoClient
from ..models.market_data import Candle
from ..models.orders import Order, OrderAction, OrderType, OrderStatus

logger = logging.getLogger(__name__)


class UniversalStrategyAdapter(BaseStrategy):
    """
    Universal adapter that wraps any TradingBot for backtesting.
    
    Features:
    - Automatic parameter mapping via introspection
    - Universal buffer system for strategies requiring historical data
    - Lifecycle hooks for light customization
    - Mock client injection
    - Standard order flow processing
    
    Use this for simple strategies. Create custom adapters only for complex cases
    requiring heavy DataFrame manipulation or multi-timeframe analysis.
    """

    def __init__(self, bot_class: Type[TradingBot], strategy_name: str = None):
        """
        Initialize universal adapter.
        
        Args:
            bot_class: The TradingBot class to instantiate (e.g., GridTradingBot)
            strategy_name: Optional name override
        """
        name = strategy_name or f"{bot_class.__name__}Adapter"
        super().__init__(name)
        
        self.bot_class = bot_class
        self.bot: Optional[TradingBot] = None
        self.current_bar: Optional[Candle] = None
        self._initialized = False
        
        # Order tracking
        self.recent_fills: Dict[str, Dict] = {}  # order_id -> fill_info
        
        # Universal buffer system (used by many strategies)
        self.buffer_enabled = False
        self.buffer_days = 90
        self.buffer_mode = "skip_initial"  # or "use_incomplete"
        self.buffer_bars_processed = 0
        self.trading_enabled = False
        self.required_buffer_bars = 0
        self.historical_data: Optional[pd.DataFrame] = None
        
        # Lifecycle hooks for customization
        self.setup_hook: Optional[Callable] = None  # Called after bot init
        self.pre_bar_hook: Optional[Callable] = None  # Called before bar processing
        self.post_bar_hook: Optional[Callable] = None  # Called after bar processing
        self.first_bar_hook: Optional[Callable] = None  # Called on first bar only
        
        # Strategy-specific state tracking (can be extended by hooks)
        self._custom_state: Dict[str, Any] = {}

    def initialize(self, **params: Any):
        """
        Initialize the TradingBot with parameters and mock client.
        Uses introspection to automatically map parameters to bot constructor.
        """
        logger.info(f"Initializing {self.name}...")
        
        # Configure buffer if enabled
        self.buffer_enabled = params.get('buffer_enabled', False)
        self.buffer_days = params.get('buffer_days', 90)
        self.buffer_mode = params.get('buffer_mode', 'skip_initial')
        
        if self.buffer_enabled:
            timeframe = params.get('timeframe', '1h')
            self.required_buffer_bars = self._calculate_buffer_bars(timeframe)
            logger.info(f"Buffer enabled: {self.buffer_days} days, "
                       f"{self.required_buffer_bars} bars required, mode={self.buffer_mode}")
        
        # Prepare bot initialization kwargs using introspection
        bot_kwargs = self._prepare_bot_kwargs(params)
        
        # Instantiate the bot
        logger.info(f"Instantiating {self.bot_class.__name__}...")
        self.bot = self.bot_class(**bot_kwargs)
        
        # Replace the live client with mock client
        self.bot.client = MockOpenAlgoClient(self)
        
        # Set bot logging level if configured
        if hasattr(self.bot, 'logger'):
            log_level = params.get('log_level', 'INFO')
            self.bot.logger.setLevel(getattr(logging, log_level))
        
        # Initialize historical data storage if buffer enabled
        if self.buffer_enabled:
            self.historical_data = pd.DataFrame()
        
        # Call setup hook if provided
        if self.setup_hook:
            logger.info("Calling setup hook...")
            self.setup_hook(self.bot, params)
        
        logger.info(f"{self.name} initialized successfully")

    def on_bar(self, candle: Candle):
        """
        Process new market data and execute strategy.
        Handles buffering, order fills, and strategy execution.
        """
        if not self.bot:
            logger.error("Strategy not initialized. Call initialize() first.")
            return
        
        self.current_bar = candle
        
        # Update buffer if enabled
        if self.buffer_enabled:
            self._update_buffer(candle)
            self.buffer_bars_processed += 1
            
            # Check if we have enough buffer data
            if not self.trading_enabled:
                if self.buffer_bars_processed >= self.required_buffer_bars:
                    self.trading_enabled = True
                    logger.info(f"Buffer complete ({self.buffer_bars_processed} bars). "
                              f"Trading enabled.")
                elif self.buffer_mode == "skip_initial":
                    # Skip trading during buffer period
                    return
                else:
                    # Use incomplete buffer
                    self.trading_enabled = True
        
        # Pre-bar hook
        if self.pre_bar_hook:
            self.pre_bar_hook(self.bot, candle)
        
        # First bar initialization
        if not self._initialized:
            self._handle_first_bar(candle)
            
            # First bar hook
            if self.first_bar_hook:
                self.first_bar_hook(self.bot, candle)
            
            self._initialized = True
            
            # Skip trading on first bar if buffer not ready
            if self.buffer_enabled and not self.trading_enabled:
                return
        
        # Skip trading if buffer not ready
        if self.buffer_enabled and not self.trading_enabled:
            return
        
        # Process filled orders
        self._process_fills()
        
        # Execute strategy logic
        self._execute_strategy_logic()
        
        # Post-bar hook
        if self.post_bar_hook:
            self.post_bar_hook(self.bot, candle)

    def _prepare_bot_kwargs(self, params: Dict) -> Dict:
        """
        Intelligently map config parameters to bot constructor arguments.
        Uses introspection to match parameter names automatically.
        
        Args:
            params: Configuration parameters
            
        Returns:
            Dictionary of kwargs for bot __init__
        """
        # Get bot constructor signature
        sig = inspect.signature(self.bot_class.__init__)
        
        # Start with dummy credentials for backtesting
        bot_kwargs = {
            'api_key': 'backtest-dummy-key',
            'host': 'http://mock-server'
        }
        
        # Map parameters from config to bot constructor
        for param_name, param_obj in sig.parameters.items():
            # Skip special parameters
            if param_name in ['self', 'api_key', 'host']:
                continue
            
            # Direct parameter mapping
            if param_name in params:
                bot_kwargs[param_name] = params[param_name]
            # Try to map common parameter variations
            elif param_name == 'state_file':
                # Use backtest-specific state file
                symbol = params.get('symbol', 'unknown')
                bot_kwargs['state_file'] = f'{self.bot_class.__name__.lower()}_backtest_{symbol}.json'
        
        logger.debug(f"Mapped bot kwargs: {list(bot_kwargs.keys())}")
        return bot_kwargs

    def _calculate_buffer_bars(self, timeframe: str) -> int:
        """
        Calculate required buffer bars based on timeframe and buffer days.
        
        Args:
            timeframe: Timeframe string (e.g., '1h', '5m', '1d')
            
        Returns:
            Number of bars required
        """
        # Parse timeframe
        timeframe_lower = timeframe.lower()
        
        # Calculate bars per day
        if timeframe_lower.endswith('m'):
            minutes = int(timeframe_lower[:-1])
            bars_per_day = (6.5 * 60) // minutes  # 6.5 hour trading day
        elif timeframe_lower.endswith('h'):
            hours = int(timeframe_lower[:-1])
            bars_per_day = 6.5 / hours
        elif timeframe_lower.endswith('d'):
            bars_per_day = 1
        else:
            logger.warning(f"Unknown timeframe format: {timeframe}, defaulting to 1h")
            bars_per_day = 6.5
        
        required_bars = int(self.buffer_days * bars_per_day)
        logger.info(f"Timeframe {timeframe}: ~{bars_per_day:.1f} bars/day, "
                   f"{required_bars} bars for {self.buffer_days} days")
        
        return required_bars

    def _update_buffer(self, candle: Candle):
        """
        Add candle to historical data buffer.
        
        Args:
            candle: Market data candle
        """
        if self.historical_data is None:
            self.historical_data = pd.DataFrame()
        
        # Convert candle to DataFrame row
        row = {
            'timestamp': candle.timestamp,
            'open': candle.open,
            'high': candle.high,
            'low': candle.low,
            'close': candle.close,
            'volume': candle.volume
        }
        
        # Append to buffer
        self.historical_data = pd.concat([
            self.historical_data,
            pd.DataFrame([row])
        ], ignore_index=True)

    def _handle_first_bar(self, candle: Candle):
        """
        Handle first bar initialization.
        Sets up initial grid, positions, or other strategy-specific setup.
        
        Args:
            candle: First market data candle
        """
        logger.info(f"Processing first bar at price: {candle.close}")
        
        # Check if bot has setup method
        if hasattr(self.bot, 'setup_grid'):
            logger.info("Setting up initial grid...")
            if not self.bot.setup_grid():
                logger.error("Failed to set up initial grid for the bot.")
                # Note: We don't stop the backtest, just log the error
        
        # Generic setup for other strategies
        elif hasattr(self.bot, 'initialize_strategy'):
            logger.info("Initializing strategy...")
            self.bot.initialize_strategy()

    def _process_fills(self):
        """
        Check for filled orders and process them.
        Delegates to bot's check_filled_orders method.
        """
        if not hasattr(self.bot, 'check_filled_orders'):
            return
        
        filled_orders = self.bot.check_filled_orders()
        
        # Clear recent fills that were processed by the bot
        if filled_orders:
            for filled_order in filled_orders:
                order_id = filled_order.get('order_id')
                if order_id and order_id in self.recent_fills:
                    del self.recent_fills[order_id]
                    logger.debug(f"Cleared processed fill {order_id}")

    def _execute_strategy_logic(self):
        """
        Execute the main strategy logic.
        Calls bot's run_backtest method for single-bar execution.
        """
        if not self.current_bar:
            logger.warning("No current bar available for strategy execution")
            return
        
        current_price = self.current_bar.close
        
        # Use the new run_backtest method (preferred)
        if hasattr(self.bot, 'run_backtest'):
            try:
                self.bot.run_backtest(current_price)
            except Exception as e:
                logger.error(f"Error in run_backtest: {e}", exc_info=True)
        
        # Fallback to grid-specific methods (for backward compatibility)
        elif hasattr(self.bot, 'check_grid_bounds'):
            try:
                bounds_status = self.bot.check_grid_bounds(current_price)
                if bounds_status != 'within':
                    self.bot.handle_breakout(current_price, bounds_status)
            except Exception as e:
                logger.error(f"Error in grid strategy execution: {e}", exc_info=True)
        
        # Generic fallback (avoid as contains loops)
        else:
            logger.warning(f"Bot {self.bot.__class__.__name__} has no run_backtest method. "
                          "Consider implementing it for better backtesting support.")

    def on_order_update(self, order: Order):
        """
        Handle order fill notification from backtest engine.
        
        Args:
            order: Filled order
        """
        # Store fill information for bot to detect
        fill_info = {
            'order_id': order.id,
            'symbol': order.symbol,
            'action': order.action.value,
            'quantity': order.quantity,
            'filled_price': order.filled_price,
            'timestamp': order.filled_at
        }
        self.recent_fills[order.id] = fill_info
        logger.debug(f"Order fill notification: {order.id} at {order.filled_price}")

    def get_state(self) -> dict:
        """
        Get current adapter state including buffer info.
        
        Returns:
            State dictionary
        """
        state = super().get_state()
        state.update({
            'buffer_enabled': self.buffer_enabled,
            'buffer_bars_processed': self.buffer_bars_processed,
            'trading_enabled': self.trading_enabled,
            'required_buffer_bars': self.required_buffer_bars,
            'custom_state': self._custom_state
        })
        
        # Include bot state if available
        if self.bot and hasattr(self.bot, 'get_performance_summary'):
            try:
                state['bot_performance'] = self.bot.get_performance_summary()
            except Exception as e:
                logger.warning(f"Could not get bot performance: {e}")
        
        return state

    def get_historical_data(self) -> Optional[pd.DataFrame]:
        """
        Get the historical data buffer.
        Useful for strategies that need access to past data.
        
        Returns:
            DataFrame with historical OHLCV data
        """
        return self.historical_data.copy() if self.historical_data is not None else None
