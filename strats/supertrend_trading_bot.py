import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging
from typing import Dict
from openalgo import api
import os

from strats.trading_bot import TradingBot

class SupertrendTradingBot(TradingBot):
    """
    A trading bot that implements the Supertrend trading strategy.
    """
    
    def __init__(self,
                 api_key: str,
                 symbol: str,
                 host: str = 'http://127.0.0.1:8800',
                 exchange: str = 'NSE',
                 state_file: str = 'supertrend_state.json',
                 take_profit_pct: float = 5.0,
                 stop_loss_pct: float = 3.0,
                 atr_period: int = 10,
                 atr_multiplier: float = 3.0,
                 max_order_amount: float = 1000.0):
        """
        Initializes the SupertrendTradingBot.

        Args:
            api_key (str): The API key for the trading platform.
            symbol (str): The trading symbol to use.
            host (str, optional): The host of the trading API. Defaults to 'http://127.0.0.1:8800'.
            exchange (str, optional): The exchange to trade on. Defaults to 'NSE'.
            state_file (str, optional): The file to save the bot's state to. Defaults to 'supertrend_state.json'.
            take_profit_pct (float, optional): The percentage to take profit at. Defaults to 5.0.
            stop_loss_pct (float, optional): The percentage to set the stop loss at. Defaults to 3.0.
            atr_period (int, optional): The period to use for the ATR calculation. Defaults to 10.
            atr_multiplier (float, optional): The multiplier to use for the Supertrend calculation. Defaults to 3.0.
            max_order_amount (float, optional): Maximum amount in rupees per trade. Defaults to 1000.0.
        """
        self.client = api(api_key, host)
        self.symbol = symbol
        self.exchange = exchange
        self.state_file = state_file
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.max_order_amount = max_order_amount
        self.state = self.load_state()
        self.ohlc_data = None
        self.is_running = False

    def calculate_supertrend(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates the Supertrend indicator for the given data.

        Args:
            data (pd.DataFrame): A DataFrame with 'high', 'low', and 'close' columns.

        Returns:
            pd.DataFrame: The input DataFrame with 'supertrend' and 'supertrend_direction' columns added.
        """
        data['tr0'] = abs(data["high"] - data["low"])
        data['tr1'] = abs(data["high"] - data["close"].shift())
        data['tr2'] = abs(data["low"] - data["close"].shift())
        data["tr"] = data[['tr0', 'tr1', 'tr2']].max(axis=1)
        data["atr"] = data["tr"].ewm(alpha=1/self.atr_period, adjust=False).mean()
        
        data['basic_upper_band'] = data['high'] + self.atr_multiplier * data['atr']
        data['basic_lower_band'] = data['low'] - self.atr_multiplier * data['atr']
        # Initialize final bands
        data['final_upper_band'] = data['basic_upper_band'].copy()
        data['final_lower_band'] = data['basic_lower_band'].copy()

        for i in range(1, len(data)):
            prev_close = data['close'].iloc[i-1]
            prev_final_upper = data['final_upper_band'].iloc[i-1]
            prev_final_lower = data['final_lower_band'].iloc[i-1]
            
            if prev_close <= prev_final_upper:
                data.iloc[i, data.columns.get_loc('final_upper_band')] = min(
                    data['basic_upper_band'].iloc[i], prev_final_upper
                )
            else:
                data.iloc[i, data.columns.get_loc('final_upper_band')] = data['basic_upper_band'].iloc[i]

            if prev_close >= prev_final_lower:
                data.iloc[i, data.columns.get_loc('final_lower_band')] = max(
                    data['basic_lower_band'].iloc[i], prev_final_lower
                )
            else:
                data.iloc[i, data.columns.get_loc('final_lower_band')] = data['basic_lower_band'].iloc[i]
            
            # Progress indicator for large datasets
            if i % 1000 == 0:
                print(f"Processed {i}/{len(data)} rows for final bands...")

        data['supertrend'] = np.nan
        data['supertrend_direction'] = 'down'

        # Calculate supertrend direction and values
        for i in range(1, len(data)):
            current_close = data['close'].iloc[i]
            prev_final_upper = data['final_upper_band'].iloc[i-1]
            prev_final_lower = data['final_lower_band'].iloc[i-1]
            prev_direction = data['supertrend_direction'].iloc[i-1]
            
            if current_close > prev_final_upper:
                data.iloc[i, data.columns.get_loc('supertrend_direction')] = 'up'
                data.iloc[i, data.columns.get_loc('supertrend')] = data['final_lower_band'].iloc[i]
            elif current_close < prev_final_lower:
                data.iloc[i, data.columns.get_loc('supertrend_direction')] = 'down'
                data.iloc[i, data.columns.get_loc('supertrend')] = data['final_upper_band'].iloc[i]
            else:
                data.iloc[i, data.columns.get_loc('supertrend_direction')] = prev_direction
                if prev_direction == 'up':
                    data.iloc[i, data.columns.get_loc('supertrend')] = data['final_lower_band'].iloc[i]
                else:
                    data.iloc[i, data.columns.get_loc('supertrend')] = data['final_upper_band'].iloc[i]
            
            # Progress indicator for large datasets
            if i % 1000 == 0:
                print(f"Processed {i}/{len(data)} rows for supertrend...")
        print("Calculated Supertrend indicator")
        return data

    def get_ohlc_data(self):
        return self.ohlc_data

    def calculate_quantity(self, current_price: float) -> int:
        """
        Calculate the number of shares to buy based on max_order_amount and current price.
        
        Args:
            current_price (float): Current price of the stock
            
        Returns:
            int: Number of shares to buy (at least 1)
        """
        if current_price <= 0:
            logging.warning(f"Invalid price {current_price}, defaulting to 1 share")
            return 1
            
        # Calculate maximum shares we can afford
        max_shares = int(self.max_order_amount / current_price)
        
        # Ensure we buy at least 1 share
        quantity = max(1, max_shares)
        
        logging.info(f"Calculated quantity: {quantity} shares (price: ₹{current_price}, max_amount: ₹{self.max_order_amount})")
        return quantity

    def place_limit_order(self, action: str, quantity: int, price: float):
        """
        Places a limit order.

        Args:
            action (str): 'buy' or 'sell'.
            quantity (int): The quantity to trade.
            price (float): The price to trade at.
        """
        try:
            order = self.client.place_order(
                symbol=self.symbol,
                exchange=self.exchange,
                action=action,
                order_type='LIMIT',
                quantity=quantity,
                price=price
            )
            logging.info(f"Placed limit order: {order}")
            self.state['orders'].append(order)
            self.save_state()
        except Exception as e:
            logging.error(f"Error placing limit order: {e}")

    def place_market_order(self, action: str, quantity: int):
        """
        Places a market order.

        Args:
            action (str): 'buy' or 'sell'.
            quantity (int): The quantity to trade.
        """
        try:
            order = self.client.place_order(
                symbol=self.symbol,
                exchange=self.exchange,
                action=action,
                order_type='MARKET',
                quantity=quantity
            )
            logging.info(f"Placed market order: {order}")
            self.state['orders'].append(order)
            self.save_state()
        except Exception as e:
            logging.error(f"Error placing market order: {e}")

    def cancel_all_orders(self):
        """
        Cancels all open orders.
        """
        try:
            self.client.cancel_all_orders(symbol=self.symbol, exchange=self.exchange)
            logging.info("Cancelled all orders.")
            self.state['orders'] = []
            self.save_state()
        except Exception as e:
            logging.error(f"Error cancelling orders: {e}")

    def check_filled_orders(self):
        """
        Checks for filled orders and updates the state.
        """
        try:
            for order in self.state['orders']:
                if order['status'] == 'OPEN':
                    filled_order = self.client.get_order_status(order['order_id'])
                    if filled_order['status'] == 'FILLED':
                        self.state['trades'].append(filled_order)
                        self.state['orders'].remove(order)
                        if filled_order['action'] == 'buy':
                            self.state['position'] += filled_order['quantity']
                        else:
                            self.state['position'] -= filled_order['quantity']
                        self.save_state()
        except Exception as e:
            logging.error(f"Error checking filled orders: {e}")

    def save_state(self):
        """
        Saves the bot's state to a file.
        """
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f)

    def load_state(self) -> Dict:
        """
        Loads the bot's state from a file.

        Returns:
            Dict: The bot's state.
        """
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                return json.load(f)
        else:
            return {'position': 0, 'orders': [], 'trades': []}

    def get_current_price(self) -> float:
        """
        Gets the current price of the trading symbol.

        Returns:
            float: The current price.
        """
        try:
            response = self.client.quotes(symbol=self.symbol, exchange=self.exchange)
            logging.debug(f"Price API response: {response}")
            
            if isinstance(response, dict) and response.get('status') == 'success':
                data = response.get('data', {})
                if 'ltp' in data:
                    price = float(data['ltp'])
                    logging.debug(f"Successfully got price: {price}")
                    return price
                else:
                    logging.error(f"No 'ltp' field in response data: {data}")
                    return 0.0
            else:
                logging.error(f"Invalid response from quotes API: {response}")
                return 0.0
        except Exception as e:
            logging.error(f"Exception getting current price: {type(e).__name__}: {e}")
            return 0.0

    def get_performance_summary(self) -> Dict:
        """
        Gets a summary of the bot's performance.

        Returns:
            Dict: A summary of the bot's performance.
        """
        realized_pnl = 0
        for trade in self.state['trades']:
            if trade['action'] == 'sell':
                realized_pnl += trade['quantity'] * trade['price']
            else:
                realized_pnl -= trade['quantity'] * trade['price']
        
        current_price = self.get_current_price()
        # Ensure current_price is valid before calculating unrealized PNL
        if not isinstance(current_price, (int, float)) or current_price <= 0:
            logging.warning(f"Invalid current price: {current_price}, using 0 for unrealized PNL")
            unrealized_pnl = 0.0
        else:
            unrealized_pnl = self.calculate_unrealized_pnl(current_price)

        return {
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_pnl,
            'total_pnl': realized_pnl + unrealized_pnl,
            'position': self.state['position'],
            'num_trades': len(self.state['trades'])
        }

    def get_trading_data_for_export(self) -> pd.DataFrame:
        """
        Gets the trading data for export.

        Returns:
            pd.DataFrame: A DataFrame of the trading data.
        """
        return pd.DataFrame(self.state['trades'])

    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """
        Calculates the unrealized profit and loss.

        Args:
            current_price (float): The current price of the trading symbol.

        Returns:
            float: The unrealized profit and loss.
        """
        # Ensure current_price is a float
        if not isinstance(current_price, (int, float)):
            logging.error(f"Invalid current_price type: {type(current_price)} - {current_price}")
            return 0.0
        
        return self.state['position'] * float(current_price)

    def run_strategy(self):
        """
        Runs the Supertrend trading strategy.

        This function checks for filled orders, fetches the latest historical data,
        calculates the Supertrend indicator, and places buy/sell orders based on the
        strategy rules.

        The function runs in an infinite loop and sleeps for 5 minutes between each
        iteration.
        """
        self.is_running = True
        while self.is_running:
            try:
                # Check for filled orders
                self.check_filled_orders()
                
                # Fetch the latest historical data
                now = datetime.now()
                from_date = now - timedelta(days=30)
                data = self.client.history(
                    symbol=self.symbol,
                    exchange=self.exchange,
                    start_date=from_date.strftime('%Y-%m-%d'),
                    end_date=now.strftime('%Y-%m-%d'),
                    interval='5m'
                )
                
                # Calculate the Supertrend indicator
                if isinstance(data, pd.DataFrame) and not data.empty:
                    df = data
                else:
                    logging.error(f"No data received from API: {data}")
                    time.sleep(60)
                    continue
                df = self.calculate_supertrend(df)
                self.ohlc_data = df
                
                # Get the last row of the DataFrame
                last_row = df.iloc[-1]
                current_price = self.get_current_price()
                
                # Skip if we can't get a valid current price
                if not isinstance(current_price, (int, float)) or current_price <= 0:
                    logging.warning(f"Invalid current price received: {current_price} (type: {type(current_price)}), skipping trade logic")
                    time.sleep(60)
                    continue

                # Check if the position is zero
                if self.state['position'] == 0:
                    # If the Supertrend direction is up, place a buy order
                    if last_row['supertrend_direction'] == 'up':
                        quantity = self.calculate_quantity(current_price)
                        self.place_market_order('buy', quantity)
                else:
                    # If the Supertrend direction is down, place a sell order
                    if last_row['supertrend_direction'] == 'down':
                        self.place_market_order('sell', abs(self.state['position']))
                    elif len(self.state['trades']) > 0:
                        # Check if the current price is above the entry price
                        # with take profit percentage
                        entry_price = self.state['trades'][-1]['price']
                        if current_price >= entry_price * (1 + self.take_profit_pct / 100):
                            self.place_market_order('sell', abs(self.state['position']))
                        # Check if the current price is below the entry price
                        # with stop loss percentage
                        elif current_price <= entry_price * (1 - self.stop_loss_pct / 100):
                            self.place_market_order('sell', abs(self.state['position']))
                
                # Sleep for 5 minutes
                time.sleep(300)
            except Exception as e:
                logging.error(f"An error occurred in the strategy loop: {e}")
                # Sleep for 1 minute
                time.sleep(60)
    
    def run_backtest(self, current_price: float):
        """
        Execute one iteration of Supertrend strategy logic for backtesting.
        
        This method contains the core strategy logic without loops or sleeps,
        designed to be called once per candle by the backtesting engine.
        The backtesting adapter should handle Supertrend calculation and maintain
        the OHLC data buffer.
        
        Args:
            current_price: Current market price for this bar
        """
        # Check for filled orders
        self.check_filled_orders()
        
        # Ensure we have OHLC data
        if self.ohlc_data is None or self.ohlc_data.empty:
            logging.warning("No OHLC data available for Supertrend calculation")
            return
        
        # Get the last row with Supertrend signal
        last_row = self.ohlc_data.iloc[-1]
        
        # Validate current price
        if not isinstance(current_price, (int, float)) or current_price <= 0:
            logging.warning(f"Invalid current price: {current_price}, skipping")
            return
        
        # Execute trading logic based on Supertrend direction
        if self.state['position'] == 0:
            # No position - check for buy signal
            if last_row['supertrend_direction'] == 'up':
                quantity = self.calculate_quantity(current_price)
                self.place_market_order('buy', quantity)
        else:
            # Have position - check for sell signal or exit conditions
            if last_row['supertrend_direction'] == 'down':
                # Supertrend sell signal
                self.place_market_order('sell', abs(self.state['position']))
            elif len(self.state['trades']) > 0:
                # Check take profit and stop loss
                entry_price = self.state['trades'][-1]['price']
                
                # Take profit
                if current_price >= entry_price * (1 + self.take_profit_pct / 100):
                    self.place_market_order('sell', abs(self.state['position']))
                # Stop loss
                elif current_price <= entry_price * (1 - self.stop_loss_pct / 100):
                    self.place_market_order('sell', abs(self.state['position']))
