# app/strategies/supertrend_strategy_adapter.py
"""
Adapter to wrap the existing SupertrendTradingBot for use in the backtesting engine.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np
import types
from strats.supertrend_trading_bot import SupertrendTradingBot
from .base_strategy import BaseStrategy
from .util.mock_openalgo_client import MockOpenAlgoClient
from ..models.market_data import Candle
from ..models.orders import Order, OrderAction, OrderType, OrderStatus

logger = logging.getLogger(__name__)


class SupertrendStrategyAdapter(BaseStrategy):
    """
    Wraps the SupertrendTradingBot to make it compatible with the backtesting engine.
    """

    def __init__(self):
        super().__init__("SupertrendStrategyAdapter")
        self.bot: Optional[SupertrendTradingBot] = None
        self.current_bar: Optional[Candle] = None
        self._initialized = False
        # Keep track of recently filled orders so bot can detect them
        self.recent_fills: Dict[str, Dict] = {}  # order_id -> fill_info
        # Store historical data for the bot's history() calls
        self.historical_data: Optional[pd.DataFrame] = None
        # Track previous Supertrend signal to detect changes
        self._previous_signal: Optional[int] = None
        # Track our position separately to sync with backtest engine
        self._current_position: int = 0
        # Buffer configuration
        self.buffer_enabled = True
        self.buffer_days = 90
        self.buffer_mode = "skip_initial"
        self.buffer_bars_processed = 0
        self.trading_enabled = False
        self.required_buffer_bars = 0

        # Win rate tracking
        self._total_trades = 0
        self._winning_trades = 0

    def initialize(self, **params: Any):
        """
        Initializes the SupertrendTradingBot with parameters and a mock client.
        """
        logger.info("Initializing SupertrendStrategyAdapter...")

        # Extract buffer configuration
        self.buffer_enabled = params.get('buffer_enabled', True)
        self.buffer_days = params.get('buffer_days', 90)
        self.buffer_mode = params.get('buffer_mode', 'skip_initial')
        
        # Calculate required buffer bars based on timeframe
        timeframe = params.get('timeframe', '1h')
        self.required_buffer_bars = self._calculate_buffer_bars(timeframe)
        
        logger.info(f"Buffer configuration: enabled={self.buffer_enabled}, "
                   f"days={self.buffer_days}, mode={self.buffer_mode}, "
                   f"required_bars={self.required_buffer_bars}")

        # The bot requires these, but they are not used in the backtest
        # as the mock client intercepts all API calls.
        dummy_api_key = "backtest-dummy-key"
        dummy_host = "http://mock-server"

        self.bot = SupertrendTradingBot(
            api_key=dummy_api_key,
            host=dummy_host,
            symbol=params.get('symbol', 'RELIANCE'),
            exchange=params.get('exchange', 'NSE'),
            state_file='supertrend_state_backtest.json',  # Use a different state file
            take_profit_pct=params.get('take_profit_pct', 5.0),
            stop_loss_pct=params.get('stop_loss_pct', 3.0),
            atr_period=params.get('atr_period', 10),
            atr_multiplier=params.get('atr_multiplier', 3.0),
            max_order_amount=params.get('max_order_amount', 1000.0)
        )

        # Replace the live client with our mock client
        self.bot.client = MockOpenAlgoClient(self)

        # Optimize the calculate_supertrend method for backtesting
        self._patch_supertrend_calculation()

        # Initialize historical data storage
        self.historical_data = pd.DataFrame()

        logger.info("SupertrendTradingBot instance created for backtesting.")
    
    def _calculate_buffer_bars(self, timeframe: str) -> int:
        """
        Calculate the number of bars needed for the buffer based on timeframe.
        """
        if not self.buffer_enabled:
            return 0
            
        # Convert timeframe to bars per day
        timeframe_to_bars = {
            '1m': 1440,   # 24*60 minutes per day
            '5m': 288,    # 1440/5
            '15m': 96,    # 1440/15
            '30m': 48,    # 1440/30
            '1h': 24,     # 24 hours per day
            '4h': 6,      # 24/4
            '1d': 1       # 1 day per day
        }
        
        bars_per_day = timeframe_to_bars.get(timeframe, 24)  # Default to hourly
        required_bars = self.buffer_days * bars_per_day
        
        logger.info(f"Calculated buffer: {self.buffer_days} days × {bars_per_day} bars/day = {required_bars} bars")
        return required_bars

    def _patch_supertrend_calculation(self):
        """
        Patch the SupertrendTradingBot's calculate_supertrend method to use optimized calculation.
        """
        def optimized_calculate_supertrend(bot_self, data: pd.DataFrame) -> pd.DataFrame:
            """
            Ultra-optimized vectorized Supertrend calculation using numpy arrays for maximum speed.
            
            Args:
                data: DataFrame with 'high', 'low', 'close' columns
                atr_period: ATR calculation period
                atr_multiplier: Multiplier for ATR in band calculation
            
            Returns:
                DataFrame with supertrend indicators added
            """
            df = data.copy()
            length = len(df)
            
            # Convert to numpy arrays for speed
            high = df['high'].values
            low = df['low'].values
            close = df['close'].values
            
            # Calculate True Range (vectorized)
            tr = np.maximum(
                high - low,
                np.maximum(
                    np.abs(high - np.roll(close, 1)),
                    np.abs(low - np.roll(close, 1))
                )
            )
            tr[0] = high[0] - low[0]  # Fix first value
            
            # Calculate ATR using pandas ewm (fastest for this operation)
            atr = pd.Series(tr).ewm(span=self.bot.atr_period, adjust=False).mean().values
            
            # Calculate basic bands
            basic_upper = high + (self.bot.atr_multiplier * atr)
            basic_lower = low - (self.bot.atr_multiplier * atr)
            
            # Initialize arrays
            final_upper = np.zeros(length)
            final_lower = np.zeros(length)
            supertrend = np.zeros(length)
            direction = np.zeros(length, dtype=int)
            
            # First values
            final_upper[0] = basic_upper[0]
            final_lower[0] = basic_lower[0]
            supertrend[0] = final_upper[0]
            direction[0] = -1
            
            # Optimized loop using numpy operations
            for i in range(1, length):
                # Final bands calculation
                if close[i-1] <= final_upper[i-1]:
                    final_upper[i] = min(basic_upper[i], final_upper[i-1])
                else:
                    final_upper[i] = basic_upper[i]
                    
                if close[i-1] >= final_lower[i-1]:
                    final_lower[i] = max(basic_lower[i], final_lower[i-1])
                else:
                    final_lower[i] = basic_lower[i]
                
                # Supertrend calculation
                if direction[i-1] == -1 and close[i] > supertrend[i-1]:
                    supertrend[i] = final_lower[i]
                    direction[i] = 1
                elif direction[i-1] == 1 and close[i] < supertrend[i-1]:
                    supertrend[i] = final_upper[i]
                    direction[i] = -1
                else:
                    supertrend[i] = final_upper[i] if direction[i-1] == -1 else final_lower[i]
                    direction[i] = direction[i-1]
            
            # Add results to dataframe
            df['tr'] = tr
            df['atr'] = atr
            df['final_upper_band'] = final_upper
            df['final_lower_band'] = final_lower
            df['supertrend'] = supertrend
            df['supertrend_direction'] = direction
            
            return df
        
        # Replace the bot's method with our optimized version
        self.bot.calculate_supertrend = types.MethodType(optimized_calculate_supertrend, self.bot)

    def on_bar(self, candle: Candle):
        """
        Called by the backtest engine for each new bar of data.
        """
        if not self.bot:
            logger.error("Strategy not initialized. Call initialize() first.")
            return

        self.current_bar = candle

        # Add the new bar to our historical data
        self._update_historical_data(candle)

        # Handle buffer logic
        if self.buffer_enabled and not self.trading_enabled:
            self.buffer_bars_processed += 1
            
            # Check if we've processed enough buffer bars
            if self.buffer_mode == "skip_initial":
                if self.buffer_bars_processed > self.required_buffer_bars:
                    self.trading_enabled = True
                    logger.info(f"Buffer period complete. Processed {self.buffer_bars_processed} bars. Trading enabled.")
                else:
                    logger.debug(f"Buffer phase: {self.buffer_bars_processed}/{self.required_buffer_bars} bars processed")
                    return  # Skip trading during buffer period
            elif self.buffer_mode == "fetch_additional":
                # For fetch_additional mode, we assume additional data was already fetched
                # and we can start trading immediately after minimum bars are available
                if len(self.historical_data) >= self.bot.atr_period + 1:
                    self.trading_enabled = True
                    logger.info(f"Sufficient data available. Trading enabled with {len(self.historical_data)} bars.")
        elif not self.buffer_enabled:
            # If buffer is disabled, enable trading once we have minimum required data
            if len(self.historical_data) >= self.bot.atr_period + 1:
                self.trading_enabled = True

        # First run: ensure we have enough data for Supertrend calculation
        if not self._initialized:
            # We need at least atr_period + 1 bars for Supertrend calculation
            required_bars = self.bot.atr_period + 1
            if len(self.historical_data) < required_bars:
                logger.debug(f"Waiting for more data. Have {len(self.historical_data)}, need {required_bars}")
                return
            
            logger.info(f"Initializing Supertrend strategy with {len(self.historical_data)} bars")
            self._initialized = True

        # Only run trading logic if trading is enabled
        if self.trading_enabled:
            self._run_supertrend_logic()
        else:
            # During buffer period, still calculate Supertrend for display but don't trade
            if len(self.historical_data) >= self.bot.atr_period + 1:
                self._calculate_supertrend_for_display()

    def _update_historical_data(self, candle: Candle):
        """
        Add the new candle to our historical data DataFrame.
        """
        new_row = pd.DataFrame({
            'timestamp': [candle.timestamp],
            'open': [candle.open],
            'high': [candle.high],
            'low': [candle.low],
            'close': [candle.close],
            'volume': [candle.volume]
        })

        if self.historical_data.empty:
            self.historical_data = new_row
        else:
            self.historical_data = pd.concat([self.historical_data, new_row], ignore_index=True)

        # Keep only the last 1000 bars to avoid memory issues
        if len(self.historical_data) > 1000:
            self.historical_data = self.historical_data.tail(1000).reset_index(drop=True)

    def _run_supertrend_logic(self):
        """
        Run the core Supertrend strategy logic adapted for backtesting.
        """
        logger.debug(f"TRADING LOGIC EVALUATION - Current bar timestamp: {self.current_bar.timestamp}, "
                    f"Price: {self.current_bar.close}, Position: {self._current_position}")
        
        try:
            # Check for filled orders first
            self.bot.check_filled_orders()

            # Calculate Supertrend on our historical data
            if len(self.historical_data) >= self.bot.atr_period + 1:
                # Use incremental calculation for better performance
                df_with_supertrend = self._calculate_supertrend_incremental()
                self.bot.ohlc_data = df_with_supertrend

                # Get the latest Supertrend signal
                last_row = df_with_supertrend.iloc[-1]
                current_price = self.current_bar.close
                current_signal = last_row['supertrend_direction']

                # Reduce debug logging frequency
                if self.context.current_tick % 1000 == 0:
                    logger.debug(f"Supertrend direction: {current_signal}, "
                               f"Previous signal: {self._previous_signal}, "
                               f"Current price: {current_price}, "
                               f"Bot position: {self.bot.state['position']}, "
                               f"Adapter position: {self._current_position}")

                # Detect signal changes
                signal_changed = self._previous_signal != current_signal
                
                if signal_changed:
                    logger.info(f"Supertrend signal changed: {self._previous_signal} -> {current_signal}")
                
                # Apply the trading logic with proper signal change detection
                if self._current_position == 0:
                    # No position: only buy on signal change to 'up'
                    if current_signal == 1 and signal_changed:  # Changed from '1' to 1
                        try:
                            # Calculate quantity based on position sizing logic
                            quantity = self.bot.calculate_quantity(current_price)
                            logger.debug(f"BUY ACTION TRIGGERED - Signal Change: {self._previous_signal} -> {current_signal}")
                            logger.debug(f"BUY ACTION DETAILS - Price: {current_price}, Position: {self._current_position}, "
                                       f"Calculated Quantity: {quantity}, Max Order Amount: ₹{self.bot.max_order_amount:,.0f}, "
                                       f"Timestamp: {self.current_bar.timestamp}")
                            logger.info(f"Supertrend signal: BUY (signal changed to up) - Quantity: {quantity} shares")
                            self.bot.place_market_order('buy', quantity)
                            logger.debug(f"BUY ORDER PLACED - Quantity: {quantity}, Type: market, Investment: ₹{quantity * current_price:,.2f}")
                        except Exception as buy_error:
                            logger.error(f"ERROR in BUY logic: {buy_error}")
                    else:
                        logger.debug(f"NO BUY ACTION - Signal: {current_signal}, Signal changed: {signal_changed}, "
                                   f"Position: {self._current_position}")

                else:
                    # Have position: check for exit conditions
                    should_sell = False
                    sell_reason = ""
                    trade_closed = False
                    trade_won = False
                    entry_price = None
                    
                    # Check for signal change to down
                    if current_signal == -1 and signal_changed:
                        should_sell = True
                        sell_reason = "signal changed to down"
                    # Check take profit and stop loss (only if we have trades)
                    elif len(self.bot.state['trades']) > 0:
                        entry_price = self.bot.state['trades'][-1]['price']
                        if current_price >= entry_price * (1 + self.bot.take_profit_pct / 100):
                            should_sell = True
                            sell_reason = f"take profit triggered at {current_price} (entry: {entry_price})"
                        elif current_price <= entry_price * (1 - self.bot.stop_loss_pct / 100):
                            should_sell = True
                            sell_reason = f"stop loss triggered at {current_price} (entry: {entry_price})"
                    
                    if should_sell:
                        logger.debug(f"SELL ACTION TRIGGERED - Reason: {sell_reason}")
                        logger.debug(f"SELL ACTION DETAILS - Price: {current_price}, Position: {self._current_position}, "
                                   f"Quantity to sell: {abs(self._current_position)}, Timestamp: {self.current_bar.timestamp}")
                        if len(self.bot.state['trades']) > 0:
                            entry_price = self.bot.state['trades'][-1]['price']
                            pnl_pct = ((current_price - entry_price) / entry_price) * 100
                            logger.debug(f"SELL ACTION P&L - Entry: {entry_price}, Current: {current_price}, "
                                       f"P&L: {pnl_pct:.2f}%")
                            # Win rate logic: count only if trade is closed (SELL)
                            self._total_trades += 1
                            if current_price > entry_price:
                                self._winning_trades += 1
                        logger.info(f"Supertrend signal: SELL ({sell_reason})")
                        self.bot.place_market_order('sell', abs(self._current_position))
                        logger.debug(f"SELL ORDER PLACED - Quantity: {abs(self._current_position)}, Type: market")
                    else:
                        logger.debug(f"NO SELL ACTION - Signal: {current_signal}, Signal changed: {signal_changed}, "
                                   f"Position: {self._current_position}, Should sell: {should_sell}")

                # Update previous signal
                self._previous_signal = int(current_signal) if current_signal is not None else None

        except Exception as e:
            logger.error(f"Error in Supertrend strategy logic: {e}")

    def _calculate_supertrend_incremental(self):
        """
        Calculate Supertrend incrementally for better performance.
        Only recalculates when we have new data or need to rebuild from scratch.
        """
        # Check if we need to recalculate everything (first time or significant data change)
        if not hasattr(self, '_cached_supertrend_data') or len(self._cached_supertrend_data) != len(self.historical_data):
            # Full calculation needed
            logger.debug(f"Full Supertrend calculation for {len(self.historical_data)} bars")
            self._cached_supertrend_data = self.bot.calculate_supertrend(self.historical_data.copy())
        else:
            # Data length matches, assume only the latest bar needs updating
            # For now, we still do full calculation but with awareness
            # TODO: Implement true incremental calculation for even better performance
            logger.debug(f"Supertrend recalculation for {len(self.historical_data)} bars")
            self._cached_supertrend_data = self.bot.calculate_supertrend(self.historical_data.copy())
        
        return self._cached_supertrend_data

    def on_order_update(self, order: Order):
        """
        Called by the backtest engine when an order's status changes.
        Synchronize position tracking between adapter and bot.
        """
        if not self.bot:
            return

        if order.status == OrderStatus.FILLED:
            logger.info(f"Adapter received fill for order {order.id} at {order.avg_fill_price}")
            logger.debug(f"ORDER FILL DEBUG - Action: {order.action.value}, Quantity: {order.quantity}, "
                        f"Price: {order.avg_fill_price}, Order ID: {order.id}")
            
            # Update our position tracking
            old_position = self._current_position
            if order.action == OrderAction.BUY:
                self._current_position += order.quantity
                logger.debug(f"BUY ORDER FILLED - Position updated: {old_position} -> {self._current_position}")
            elif order.action == OrderAction.SELL:
                self._current_position -= order.quantity
                logger.debug(f"SELL ORDER FILLED - Position updated: {old_position} -> {self._current_position}")
            
            # Keep bot's position in sync with ours
            self.bot.state['position'] = self._current_position
            
            # Store the fill info so the bot can detect it
            self.recent_fills[order.id] = {
                'price': order.avg_fill_price,
                'action': order.action.value.lower(),
                'quantity': order.quantity,
                'timestamp': datetime.now()
            }
            
            # Add to bot's trades list for take profit/stop loss calculations
            trade_record = {
                'order_id': order.id,
                'action': order.action.value.lower(),
                'quantity': order.quantity,
                'price': order.avg_fill_price,
                'timestamp': datetime.now().isoformat()
            }
            self.bot.state['trades'].append(trade_record)
            
            logger.info(f"Position updated: {self._current_position} shares")
            
        elif order.status == OrderStatus.CANCELLED:
            logger.debug(f"Adapter received cancel for order {order.id}")

        elif order.status == OrderStatus.REJECTED:
            logger.warning(f"Adapter received rejection for order {order.id}")

    def _calculate_supertrend_for_display(self):
        """
        Calculate Supertrend during buffer period for display purposes only.
        This helps maintain signal tracking without executing trades.
        """
        try:
            if len(self.historical_data) >= self.bot.atr_period + 1:
                df_with_supertrend = self._calculate_supertrend_incremental()
                self.bot.ohlc_data = df_with_supertrend

                # Update signal tracking for consistency
                last_row = df_with_supertrend.iloc[-1]
                current_signal = last_row['supertrend_direction']
                
                if self._previous_signal != current_signal:
                    logger.debug(f"Supertrend signal (buffer): {self._previous_signal} -> {current_signal}")
                    self._previous_signal = int(current_signal) if current_signal is not None else None
                    
        except Exception as e:
            logger.error(f"Error calculating Supertrend for display: {e}")

    def get_state(self) -> dict:
        """
        Get current strategy state including bot state, position tracking, and win rate.
        """
        base_state = super().get_state()
        if self.bot:
            win_rate = float((self._winning_trades / self._total_trades * 100) if self._total_trades > 0 else 0.0)
            base_state.update({
                'bot_position': int(self.bot.state['position']),
                'adapter_position': int(self._current_position),
                'bot_trades': int(len(self.bot.state['trades'])),
                'recent_fills': int(len(self.recent_fills)),
                'historical_bars': int(len(self.historical_data)) if self.historical_data is not None else 0,
                'previous_signal': int(self._previous_signal) if self._previous_signal is not None else None,
                'position_sync': bool(self.bot.state['position'] == self._current_position),
                'buffer_enabled': bool(self.buffer_enabled),
                'buffer_bars_processed': int(self.buffer_bars_processed),
                'required_buffer_bars': int(self.required_buffer_bars),
                'trading_enabled': bool(self.trading_enabled),
                'buffer_progress': f"{self.buffer_bars_processed}/{self.required_buffer_bars}" if self.buffer_enabled else "N/A",
                'win_rate': win_rate,
                'winning_trades': int(self._winning_trades),
                'total_trades': int(self._total_trades)
            })
        return base_state
