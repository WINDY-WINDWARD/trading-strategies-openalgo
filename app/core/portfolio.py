# app/core/portfolio.py
"""
Portfolio management and position tracking.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import logging
from ..models.orders import Order, OrderAction
from ..models.market_data import Candle


logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Position in a single symbol."""
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    total_cost: float = 0.0
    realized_pnl: float = 0.0
    last_price: float = 0.0
    
    @property
    def market_value(self) -> float:
        """Current market value of position."""
        return self.quantity * self.last_price
    
    @property
    def unrealized_pnl(self) -> float:
        """Unrealized P&L."""
        if self.quantity == 0:
            return 0.0
        return (self.last_price - self.avg_price) * self.quantity
    
    @property
    def total_pnl(self) -> float:
        """Total P&L (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl
    
    def update_price(self, price: float) -> None:
        """Update last price."""
        self.last_price = price
    
    def add_shares(self, quantity: float, price: float) -> None:
        """Add shares to position."""
        if self.quantity == 0:
            # New position
            self.quantity = quantity
            self.avg_price = price
            self.total_cost = quantity * price
        else:
            # Add to existing position
            total_value = self.total_cost + (quantity * price)
            self.quantity += quantity
            self.avg_price = total_value / self.quantity if self.quantity != 0 else 0
            self.total_cost = total_value
    
    def remove_shares(self, quantity: float, price: float) -> float:
        """
        Remove shares from position and calculate realized P&L.
        
        Args:
            quantity: Number of shares to remove (positive)
            price: Price at which shares are removed
            
        Returns:
            Realized P&L from this transaction
        """
        if quantity > abs(self.quantity):
            raise ValueError(f"Cannot remove {quantity} shares, only {abs(self.quantity)} available")
        
        # Calculate realized P&L
        pnl = (price - self.avg_price) * quantity
        self.realized_pnl += pnl
        
        # Update position
        self.quantity -= quantity
        
        if abs(self.quantity) < 1e-8:  # Essentially zero
            # Position closed
            self.quantity = 0.0
            self.avg_price = 0.0
            self.total_cost = 0.0
        else:
            # Partial close - avg_price remains same
            self.total_cost = self.quantity * self.avg_price
        
        return pnl
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'quantity': self.quantity,
            'avg_price': self.avg_price,
            'total_cost': self.total_cost,
            'market_value': self.market_value,
            'unrealized_pnl': self.unrealized_pnl,
            'realized_pnl': self.realized_pnl,
            'total_pnl': self.total_pnl,
            'last_price': self.last_price
        }


class Portfolio:
    """
    Portfolio manager for tracking positions, cash, and P&L.
    """
    
    def __init__(self, initial_cash: float = 100000.0):
        """
        Initialize portfolio.
        
        Args:
            initial_cash: Starting cash amount
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        
        # Tracking
        self.total_commission = 0.0
        self.equity_curve: List[Dict] = []
        self.trades: List[Dict] = []
        self.peak_equity = initial_cash
        self.max_drawdown = 0.0
        
        logger.info(f"Portfolio initialized with ₹{initial_cash:,.2f}")
    
    @property
    def total_positions_value(self) -> float:
        """Total value of all positions at current prices."""
        return sum(pos.market_value for pos in self.positions.values())
    
    @property
    def total_equity(self) -> float:
        """Total portfolio equity."""
        return self.cash + self.total_positions_value
    
    @property
    def total_unrealized_pnl(self) -> float:
        """Total unrealized P&L."""
        return sum(pos.unrealized_pnl for pos in self.positions.values())
    
    @property
    def total_realized_pnl(self) -> float:
        """Total realized P&L."""
        return sum(pos.realized_pnl for pos in self.positions.values())
    
    @property
    def total_pnl(self) -> float:
        """Total P&L."""
        return self.total_equity - self.initial_cash
    
    @property
    def current_drawdown(self) -> float:
        """Current drawdown from peak."""
        return self.peak_equity - self.total_equity
    
    @property
    def current_drawdown_pct(self) -> float:
        """Current drawdown percentage."""
        if self.peak_equity == 0:
            return 0.0
        return (self.current_drawdown / self.peak_equity) * 100
    
    def update_prices(self, candle: Candle) -> None:
        """
        Update position prices with new market data.
        
        Args:
            candle: New market data candle
        """
        symbol = candle.symbol
        
        if symbol in self.positions:
            self.positions[symbol].update_price(candle.close)
        
        # Update equity curve and drawdown tracking
        current_equity = self.total_equity
        
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        drawdown = self.current_drawdown
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
        
        # Record equity point
        self.equity_curve.append({
            'timestamp': candle.timestamp,
            'equity': current_equity,
            'cash': self.cash,
            'positions_value': self.total_positions_value,
            'unrealized_pnl': self.total_unrealized_pnl,
            'drawdown': drawdown,
            'drawdown_pct': self.current_drawdown_pct
        })
    
    def execute_order(self, order: Order, fill_price: float, commission: float = 0.0) -> bool:
        """
        Execute an order against the portfolio.
        
        Args:
            order: Order to execute
            fill_price: Price at which order is filled
            commission: Commission charged for trade
            
        Returns:
            True if execution successful
        """
        try:
            symbol = order.symbol
            quantity = order.filled_quantity  # Use filled quantity
            
            # Calculate total cost including commission
            trade_value = quantity * fill_price
            total_cost = trade_value + commission
            
            # Check if we have enough cash for buy orders
            if order.action == OrderAction.BUY:
                if self.cash < total_cost:
                    logger.warning(f"Insufficient cash for order {order.id}: need ₹{total_cost:.2f}, have ₹{self.cash:.2f}")
                    return False
                
                # Deduct cash and add position
                self.cash -= total_cost
                
                # Add to position
                if symbol not in self.positions:
                    self.positions[symbol] = Position(symbol)
                
                self.positions[symbol].add_shares(quantity, fill_price)
                
            else:  # SELL
                # Check if we have enough shares
                if symbol not in self.positions or self.positions[symbol].quantity < quantity:
                    available = self.positions[symbol].quantity if symbol in self.positions else 0
                    logger.warning(f"Insufficient shares for order {order.id}: need {quantity}, have {available}")
                    return False
                
                # Remove shares and calculate realized P&L
                realized_pnl = self.positions[symbol].remove_shares(quantity, fill_price)
                
                # Add cash from sale (minus commission)
                self.cash += trade_value - commission
            
            # Record commission
            self.total_commission += commission
            
            # Record trade
            trade = {
                'timestamp': order.filled_at or datetime.now(),
                'order_id': order.id,
                'symbol': symbol,
                'action': order.action.value,
                'quantity': quantity,
                'price': fill_price,
                'value': trade_value,
                'commission': commission,
                'realized_pnl': realized_pnl if order.action == OrderAction.SELL else 0.0
            }
            self.trades.append(trade)
            
            logger.debug(f"Executed {order.action.value} {quantity} {symbol} @ {fill_price:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Error executing order {order.id}: {e}")
            return False
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for symbol.
        
        Args:
            symbol: Symbol to get position for
            
        Returns:
            Position object or None if no position
        """
        return self.positions.get(symbol)
    
    def get_available_cash(self) -> float:
        """Get available cash."""
        return self.cash
    
    def get_portfolio_summary(self) -> Dict:
        """
        Get portfolio summary.
        
        Returns:
            Dictionary with portfolio summary
        """
        return {
            'initial_cash': self.initial_cash,
            'current_cash': self.cash,
            'positions_value': self.total_positions_value,
            'total_equity': self.total_equity,
            'total_pnl': self.total_pnl,
            'total_pnl_pct': (self.total_pnl / self.initial_cash) * 100,
            'unrealized_pnl': self.total_unrealized_pnl,
            'realized_pnl': self.total_realized_pnl,
            'total_commission': self.total_commission,
            'max_drawdown': self.max_drawdown,
            'max_drawdown_pct': (self.max_drawdown / self.peak_equity) * 100 if self.peak_equity > 0 else 0,
            'current_drawdown': self.current_drawdown,
            'current_drawdown_pct': self.current_drawdown_pct,
            'num_positions': len([p for p in self.positions.values() if p.quantity != 0]),
            'num_trades': len(self.trades)
        }
    
    def get_positions_summary(self) -> List[Dict]:
        """
        Get summary of all positions.
        
        Returns:
            List of position dictionaries
        """
        return [pos.to_dict() for pos in self.positions.values() if pos.quantity != 0]
    
    def reset(self, initial_cash: Optional[float] = None) -> None:
        """
        Reset portfolio to initial state.
        
        Args:
            initial_cash: New initial cash amount (optional)
        """
        if initial_cash is not None:
            self.initial_cash = initial_cash
        
        self.cash = self.initial_cash
        self.positions.clear()
        self.total_commission = 0.0
        self.equity_curve.clear()
        self.trades.clear()
        self.peak_equity = self.initial_cash
        self.max_drawdown = 0.0
        
        logger.info(f"Portfolio reset with ₹{self.initial_cash:,.2f}")
    
    def to_dict(self) -> Dict:
        """Convert portfolio to dictionary."""
        return {
            'summary': self.get_portfolio_summary(),
            'positions': self.get_positions_summary(),
            'equity_curve': self.equity_curve,
            'trades': self.trades
        }
