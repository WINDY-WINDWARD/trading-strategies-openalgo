# app/strategies/base_strategy.py
"""
Base strategy interface for backtesting.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Any
from ..models.orders import Order
from ..models.market_data import Candle


class BaseStrategy(ABC):
    """
    Base strategy interface that all strategies must implement.
    """
    
    def __init__(self, name: str = "BaseStrategy"):
        """
        Initialize strategy.
        
        Args:
            name: Strategy name
        """
        self.name = name
        self.context: Optional[Any] = None
        self._initialized = False
    
    @abstractmethod
    def initialize(self, **kwargs) -> None:
        """
        Initialize strategy with parameters.
        
        Args:
            **kwargs: Strategy parameters
        """
        pass
    
    @abstractmethod
    def on_bar(self, candle: Candle) -> None:
        """
        Process new market data and generate orders.
        
        Args:
            candle: New market data candle
        """
        pass
    
    def on_order_update(self, order: Order) -> None:
        """
        Handle order fill notification.
        
        Args:
            order: Filled order
        """
        # Default implementation does nothing
        pass
    
    def set_context(self, context: Any) -> None:
        """
        Set the backtest engine context for the strategy to interact with.
        This allows submitting orders, accessing portfolio, etc.
        """
        self.context = context
    
    def submit_order(self, order: Order) -> bool:
        """Submit an order through the backtest engine."""
        if self.context:
            return self.context.submit_order(order)
        return False

    def cancel_all_orders(self) -> List[str]:
        if self.context:
            # This is a simplified implementation. A real one might be more complex.
            cancelled_ids = []
            for oid in list(self.context.active_orders.keys()):
                if self.context.cancel_order(oid):
                    cancelled_ids.append(oid)
            return cancelled_ids
        return []

    def get_orders(self) -> List[Order]:
        if self.context:
            return list(self.context.active_orders.values())
        return []
    
    def get_state(self) -> dict:
        """
        Get current strategy state.
        
        Returns:
            Strategy state dictionary
        """
        return {
            'name': self.name,
            'initialized': self._initialized
        }
    
    def load_state(self, state: dict) -> None:
        """
        Load strategy state.
        
        Args:
            state: Strategy state dictionary
        """
        self.name = state.get('name', self.name)
        self._initialized = state.get('initialized', False)
