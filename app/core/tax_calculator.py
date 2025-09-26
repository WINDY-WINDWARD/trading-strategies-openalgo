# app/core/tax_calculator.py
"""
Tax calculator for delivery and intraday trading taxes.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
from dataclasses import dataclass, field
import logging

from ..models.orders import OrderAction


logger = logging.getLogger(__name__)


@dataclass
class DailyPosition:
    """Position tracking for a single day."""
    date: date
    symbol: str
    opening_quantity: float = 0.0  # Position at start of day
    bought_today: float = 0.0  # Shares bought during the day
    sold_today: float = 0.0  # Shares sold during the day
    closing_quantity: float = 0.0  # Position at end of day
    last_price: float = 0.0  # Last price for the day
    delivery_tax_paid: float = 0.0  # Delivery tax already paid on opening position
    intraday_tax_accrued: float = 0.0  # Intraday tax for shares sold today
    delivery_tax_accrued: float = 0.0  # Delivery tax for closing position


@dataclass
class TaxSummary:
    """Tax calculation summary."""
    total_delivery_tax: float = 0.0
    total_intraday_tax: float = 0.0
    delivery_trades_count: int = 0
    intraday_trades_count: int = 0
    total_tax_payable: float = 0.0


class TaxCalculator:
    """
    Calculates delivery and intraday taxes based on trading activity.
    
    Logic:
    - Track daily positions for each symbol
    - Delivery tax: Applied to shares held at end of day
    - Intraday tax: Applied to shares bought and sold on same day
    - When selling: Prioritize delivery shares (from previous day) first
    - Delivery shares sold next day incur additional transaction cost over existing delivery tax
    """

    def __init__(self, delivery_tax_pct: float = 0.1, intraday_tax_pct: float = 0.025):
        """
        Initialize tax calculator.
        
        Args:
            delivery_tax_pct: Delivery tax percentage (e.g., 0.1 for 0.1%)
            intraday_tax_pct: Intraday tax percentage (e.g., 0.025 for 0.025%)
        """
        self.delivery_tax_pct = delivery_tax_pct
        self.intraday_tax_pct = intraday_tax_pct
        
        # Track positions by symbol and date
        self.daily_positions: Dict[str, Dict[date, DailyPosition]] = {}
        
        # Overall tax summary
        self.tax_summary = TaxSummary()
        
        logger.info(f"TaxCalculator initialized: delivery={delivery_tax_pct}%, intraday={intraday_tax_pct}%")

    def process_trade(self, symbol: str, action: OrderAction, quantity: float, 
                     price: float, timestamp: datetime) -> float:
        """
        Process a trade and calculate applicable taxes.
        
        Args:
            symbol: Trading symbol
            action: BUY or SELL
            quantity: Trade quantity
            price: Trade price
            timestamp: Trade timestamp
            
        Returns:
            Tax amount for this trade
        """
        trade_date = timestamp.date()
        trade_value = quantity * price
        
        # Initialize daily position if needed
        if symbol not in self.daily_positions:
            self.daily_positions[symbol] = {}
        
        if trade_date not in self.daily_positions[symbol]:
            # Get previous day's closing position
            prev_date = self._get_previous_trading_day(symbol, trade_date)
            opening_quantity = 0.0
            delivery_tax_paid = 0.0
            
            if prev_date and prev_date in self.daily_positions[symbol]:
                prev_position = self.daily_positions[symbol][prev_date]
                opening_quantity = prev_position.closing_quantity
                delivery_tax_paid = prev_position.delivery_tax_accrued
            
            self.daily_positions[symbol][trade_date] = DailyPosition(
                date=trade_date,
                symbol=symbol,
                opening_quantity=opening_quantity,
                delivery_tax_paid=delivery_tax_paid
            )
        
        position = self.daily_positions[symbol][trade_date]
        
        if action == OrderAction.BUY:
            return self._process_buy(position, quantity, price)
        else:  # SELL
            return self._process_sell(position, quantity, price)

    def _process_buy(self, position: DailyPosition, quantity: float, price: float) -> float:
        """
        Process a buy trade.
        
        Args:
            position: Daily position object
            quantity: Buy quantity
            price: Buy price
            
        Returns:
            Tax amount (0 for buys)
        """
        position.bought_today += quantity
        position.closing_quantity += quantity
        
        # No tax on buys
        return 0.0

    def _process_sell(self, position: DailyPosition, quantity: float, price: float) -> float:
        """
        Process a sell trade.
        
        Args:
            position: Daily position object
            quantity: Sell quantity
            price: Sell price
            
        Returns:
            Tax amount for this sell
        """
        trade_value = quantity * price
        total_tax = 0.0
        
        # Initialize variables
        delivery_sell_quantity = 0.0
        intraday_sell_quantity = 0.0
        
        # First, sell from opening position (delivery shares)
        delivery_sell_quantity = min(quantity, position.opening_quantity)
        if delivery_sell_quantity > 0:
            # Delivery tax already paid, but additional transaction cost
            delivery_tax = (delivery_sell_quantity * price) * (self.intraday_tax_pct / 100.0)
            position.delivery_tax_accrued += delivery_tax
            total_tax += delivery_tax
            position.opening_quantity -= delivery_sell_quantity
            quantity -= delivery_sell_quantity
            self.tax_summary.delivery_trades_count += 1
        
        # Then sell from today's buys (intraday)
        if quantity > 0:
            intraday_sell_quantity = min(quantity, position.bought_today)
            if intraday_sell_quantity > 0:
                intraday_tax = (intraday_sell_quantity * price) * (self.intraday_tax_pct / 100.0)
                position.intraday_tax_accrued += intraday_tax
                total_tax += intraday_tax
                position.bought_today -= intraday_sell_quantity
                quantity -= intraday_sell_quantity
                self.tax_summary.intraday_trades_count += 1
        
        # Update closing quantity
        position.closing_quantity -= (delivery_sell_quantity + intraday_sell_quantity)
        position.sold_today += (delivery_sell_quantity + intraday_sell_quantity)
        
        return total_tax

    def process_end_of_day(self, symbol: str, current_date: date) -> float:
        """
        Process end of day for a symbol and calculate delivery tax on remaining positions.
        
        Args:
            symbol: Trading symbol
            current_date: Current date
            
        Returns:
            Delivery tax for positions held overnight
        """
        if symbol not in self.daily_positions or current_date not in self.daily_positions[symbol]:
            return 0.0
        
        position = self.daily_positions[symbol][current_date]
        
        # Calculate delivery tax on closing position
        if position.closing_quantity > 0:
            delivery_tax = (position.closing_quantity * position.last_price) * (self.delivery_tax_pct / 100.0)
            position.delivery_tax_accrued += delivery_tax
            self.tax_summary.total_delivery_tax += delivery_tax
            return delivery_tax
        
        return 0.0

    def get_tax_summary(self) -> TaxSummary:
        """
        Get overall tax summary.
        
        Returns:
            TaxSummary object
        """
        # Calculate totals
        self.tax_summary.total_intraday_tax = sum(
            pos.intraday_tax_accrued 
            for symbol_positions in self.daily_positions.values()
            for pos in symbol_positions.values()
        )
        
        self.tax_summary.total_delivery_tax = sum(
            pos.delivery_tax_accrued 
            for symbol_positions in self.daily_positions.values()
            for pos in symbol_positions.values()
        )
        
        self.tax_summary.total_tax_payable = (
            self.tax_summary.total_delivery_tax + self.tax_summary.total_intraday_tax
        )
        
        return self.tax_summary

    def _get_previous_trading_day(self, symbol: str, current_date: date) -> Optional[date]:
        """
        Get the previous trading day for a symbol.
        
        Args:
            symbol: Trading symbol
            current_date: Current date
            
        Returns:
            Previous trading day or None
        """
        # Simple implementation - in real trading, would check market calendar
        # For now, assume previous day if it exists in our records
        from datetime import timedelta
        
        prev_date = current_date - timedelta(days=1)
        if symbol in self.daily_positions and prev_date in self.daily_positions[symbol]:
            return prev_date
        return None

    def reset(self) -> None:
        """Reset the tax calculator."""
        self.daily_positions.clear()
        self.tax_summary = TaxSummary()
        logger.info("TaxCalculator reset")