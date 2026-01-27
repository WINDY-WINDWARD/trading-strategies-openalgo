# app/core/order_simulator.py
"""
Order execution simulator with realistic market impact and slippage.
"""

import random
from typing import Optional, Tuple, List
from datetime import datetime
import logging
from ..models.orders import Order, OrderStatus, OrderType, OrderAction
from ..models.market_data import Candle
from ..core.events import FillEvent


logger = logging.getLogger(__name__)


class OrderSimulator:
    """
    Simulates order execution with realistic market conditions.
    
    Features:
    - Slippage modeling
    - Partial fills
    - Market impact
    - Order rejection scenarios
    """
    
    def __init__(
        self,
        slippage_bps: float = 2.0,
        min_fill_ratio: float = 0.1,
        max_fill_ratio: float = 1.0,
        market_impact_factor: float = 0.1,
        seed: Optional[int] = None
    ):
        """
        Initialize order simulator.
        
        Args:
            slippage_bps: Slippage in basis points
            min_fill_ratio: Minimum fill ratio for partial fills
            max_fill_ratio: Maximum fill ratio
            market_impact_factor: Market impact factor
            seed: Random seed for reproducible behavior
        """
        self.slippage_bps = slippage_bps
        self.min_fill_ratio = min_fill_ratio
        self.max_fill_ratio = max_fill_ratio
        self.market_impact_factor = market_impact_factor
        
        if seed is not None:
            random.seed(seed)
        
        logger.info(f"Order simulator initialized: slippage={slippage_bps}bps, impact={market_impact_factor}")
    
    def simulate_execution(
        self,
        order: Order,
        candle: Candle,
        volume_ratio: float = 0.01
    ) -> Optional[FillEvent]:
        """
        Simulate order execution against market data.
        
        Args:
            order: Order to execute
            candle: Current market candle
            volume_ratio: Fraction of candle volume we can consume
            
        Returns:
            FillEvent if order executed, None if not filled
        """
        if not order.is_active:
            return None
        
        # Determine execution price
        execution_price = self._calculate_execution_price(order, candle)
        
        if execution_price is None:
            # Order not executable at current prices
            return None
        
        # Calculate fill quantity
        fill_quantity = self._calculate_fill_quantity(
            order, candle, volume_ratio
        )
        
        if fill_quantity <= 0:
            return None
        
        # Apply slippage
        slipped_price = self._apply_slippage(execution_price, order.action, fill_quantity)
        
        # Create fill event
        fill_event = FillEvent(
            order_id=order.id,
            fill_price=slipped_price,
            fill_quantity=fill_quantity,
            commission=0.0,  # Commission calculated elsewhere
            timestamp=candle.timestamp
        )
        
        # Update order
        order.fill(fill_quantity, slipped_price, candle.timestamp)
        
        logger.debug(f"Simulated fill: {order.action.value} {fill_quantity} {order.symbol} @ {slipped_price:.2f}")
        
        return fill_event
    
    def _calculate_execution_price(self, order: Order, candle: Candle) -> Optional[float]:
        """
        Calculate execution price based on order type and market conditions.
        
        Args:
            order: Order to execute
            candle: Current market candle
            
        Returns:
            Execution price or None if not executable
        """
        if order.order_type == OrderType.MARKET:
            # Market orders execute at current price with some randomness
            if order.action == OrderAction.BUY:
                # Buy at ask (approximated as close + small spread)
                spread = (candle.high - candle.low) * 0.01  # Small spread
                return candle.close + spread
            else:
                # Sell at bid
                spread = (candle.high - candle.low) * 0.01
                return candle.close - spread
        
        elif order.order_type == OrderType.LIMIT:
            if order.price is None:
                return None
            
            if order.action == OrderAction.BUY:
                # Buy limit executes if market goes to or below limit price
                # Only execute if the low of the candle reached our limit price or better
                if candle.low <= order.price:
                    # Execute at the better of limit price or actual low (more realistic)
                    return min(order.price, candle.low)
            else:
                # Sell limit executes if market goes to or above limit price
                # Only execute if the high of the candle reached our limit price or better
                if candle.high >= order.price:
                    # Execute at the better of limit price or actual high (more realistic)
                    return max(order.price, candle.high)
        
        return None
    
    def _calculate_fill_quantity(
        self,
        order: Order,
        candle: Candle,
        volume_ratio: float
    ) -> float:
        """
        Calculate how much of the order can be filled based on available volume.
        
        Args:
            order: Order to fill
            candle: Current market candle
            volume_ratio: Maximum fraction of candle volume we can consume
            
        Returns:
            Quantity that can be filled
        """
        remaining_quantity = order.remaining_quantity
        
        if remaining_quantity <= 0:
            return 0.0
        
        # Calculate maximum quantity based on market volume
        max_volume_quantity = candle.volume * volume_ratio
        
        # For small orders relative to volume, fill completely
        if remaining_quantity <= max_volume_quantity * 0.1:
            fill_ratio = 1.0
        else:
            # Larger orders may get partial fills
            # Higher volatility = easier to fill
            volatility = (candle.high - candle.low) / candle.close
            base_fill_ratio = min(max_volume_quantity / remaining_quantity, 1.0)
            
            # Add some randomness
            randomness = random.uniform(0.8, 1.2)
            fill_ratio = min(base_fill_ratio * randomness, 1.0)
            
            # Ensure minimum fill ratio
            fill_ratio = max(fill_ratio, self.min_fill_ratio)
            fill_ratio = min(fill_ratio, self.max_fill_ratio)
        
        fill_quantity = remaining_quantity * fill_ratio
        
        # Round to reasonable precision
        return round(fill_quantity, 2)
    
    def _apply_slippage(
        self,
        base_price: float,
        action: OrderAction,
        quantity: float
    ) -> float:
        """
        Apply slippage and market impact to execution price.
        
        Args:
            base_price: Base execution price
            action: Order action
            quantity: Fill quantity
            
        Returns:
            Price after slippage
        """
        # Base slippage
        slippage_factor = self.slippage_bps / 10000.0  # Convert bps to decimal
        
        # Market impact based on order size (simplified model)
        impact_factor = self.market_impact_factor * min(quantity / 1000.0, 1.0)
        
        # Total slippage
        total_slippage = slippage_factor + impact_factor
        
        # Add some randomness
        random_factor = random.uniform(0.5, 1.5)
        total_slippage *= random_factor
        
        # Apply slippage based on side
        if action == OrderAction.BUY:
            # Buy orders pay more (worse price)
            slipped_price = base_price * (1 + total_slippage)
        else:
            # Sell orders receive less (worse price)
            slipped_price = base_price * (1 - total_slippage)
        
        return round(slipped_price, 2)
    
    def should_reject_order(self, order: Order, candle: Candle) -> bool:
        """
        Determine if order should be rejected based on market conditions.
        
        Args:
            order: Order to check
            candle: Current market candle
            
        Returns:
            True if order should be rejected
        """
        # Simple rejection scenarios
        
        # Reject orders far from market
        if order.order_type == OrderType.LIMIT and order.price is not None:
            price_diff_pct = abs(order.price - candle.close) / candle.close
            
            # Reject if limit price is more than 10% away from market
            if price_diff_pct > 0.10:
                return True
        
        # Reject very large orders occasionally (liquidity constraints)
        if order.quantity > 10000:  # Arbitrary large size
            if random.random() < 0.05:  # 5% chance of rejection
                return True
        
        return False
    
    def get_simulator_stats(self) -> dict:
        """
        Get simulator statistics.
        
        Returns:
            Dictionary with simulator statistics
        """
        return {
            'slippage_bps': self.slippage_bps,
            'min_fill_ratio': self.min_fill_ratio,
            'max_fill_ratio': self.max_fill_ratio,
            'market_impact_factor': self.market_impact_factor
        }
