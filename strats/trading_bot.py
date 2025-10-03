# this is the superclass for trading bots all trading bots should inherit from this class and implement the abstract methods
from abc import ABC, abstractmethod

class TradingBot(ABC):

    @abstractmethod
    def place_market_order(self, action, quantity):
        pass

    @abstractmethod
    def place_limit_order(self, action, quantity, price):
        pass

    @abstractmethod
    def cancel_all_orders(self):
        pass

    @abstractmethod
    def check_filled_orders(self):
        pass
    
    @abstractmethod
    def save_state(self):
        pass

    @abstractmethod
    def load_state(self):
        pass

    @abstractmethod
    def get_current_price(self):
        pass

    @abstractmethod
    def get_performance_summary(self):
        pass
    
    @abstractmethod
    def get_trading_data_for_export(self):
        pass

    @abstractmethod
    def calculate_unrealized_pnl(self, current_price):
        pass

    @abstractmethod
    def run_strategy(self):
        """Execute live trading strategy (usually contains infinite loop)."""
        pass
    
    @abstractmethod
    def run_backtest(self, current_price):
        """
        Execute one iteration of strategy logic for backtesting.
        
        This method should execute the strategy logic for a single bar/tick
        without any loops or sleeps. It's called by the backtesting engine
        for each candle.
        
        Args:
            current_price: Current market price for this iteration
            
        Returns:
            None
        """
        pass