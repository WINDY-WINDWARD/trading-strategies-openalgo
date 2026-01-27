#!/usr/bin/env python3
"""
Test script to verify that orders are not executed immediately upon submission
but wait for proper price triggers.
"""

import uuid
import sys
import os
from datetime import datetime, timedelta

# Add the project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.config import AppConfig, BacktestConfig, DataConfig, OpenAlgoConfig, StrategyConfig, UIConfig, LoggingConfig
from app.models.market_data import Candle
from app.models.orders import Order, OrderAction, OrderType, OrderStatus
from app.core.backtest_engine import BacktestEngine
from app.strategies.base_strategy import BaseStrategy


class TestStrategy(BaseStrategy):
    """Test strategy to verify tick-based order execution behavior."""
    
    def __init__(self):
        super().__init__("TestTickStrategy")
        self.candle_count = 0
        self.orders_submitted = []
        self.orders_filled = []
        self.tick_data = []
    
    def initialize(self, **kwargs):
        self._initialized = True
    
    def on_bar(self, candle: Candle):
        self.candle_count += 1
        current_tick = self.context.get_current_tick() if self.context else 0
        
        # Record tick data
        tick_info = self.context.get_tick_info() if self.context else {}
        self.tick_data.append({
            'tick': current_tick,
            'candle_count': self.candle_count,
            'price': candle.close,
            'timestamp': candle.timestamp,
            'active_orders': tick_info.get('active_orders_count', 0)
        })
        
        print(f"Tick {current_tick} - Candle {self.candle_count}: Price = {candle.close}, Active orders: {tick_info.get('active_orders_count', 0)}")
        
        # On first tick, place orders
        if current_tick == 1:
            print(f"  Tick {current_tick}: Placing orders...")
            
            # Buy limit order 5% below current price
            buy_price = candle.close * 0.95
            buy_order = Order(
                id=str(uuid.uuid4()),
                symbol="TEST",
                exchange="TEST",
                action=OrderAction.BUY,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=buy_price
            )
            
            # Sell limit order 5% above current price  
            sell_price = candle.close * 1.05
            sell_order = Order(
                id=str(uuid.uuid4()),
                symbol="TEST",
                exchange="TEST", 
                action=OrderAction.SELL,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=sell_price
            )
            
            print(f"    Submitting BUY order @ {buy_price:.2f} (current: {candle.close:.2f})")
            print(f"    Submitting SELL order @ {sell_price:.2f} (current: {candle.close:.2f})")
            
            self.submit_order(buy_order)
            self.submit_order(sell_order)
            self.orders_submitted.extend([buy_order, sell_order])
            
        # Show active orders for each tick
        if current_tick <= 5:
            active_orders = self.get_orders()
            if active_orders:
                for order in active_orders:
                    print(f"    Active: {order.action.value} @ {order.price:.2f} - Status: {order.status.value}")
    
    def on_order_update(self, order: Order):
        if order.status == OrderStatus.FILLED:
            current_tick = self.context.get_current_tick() if self.context else 0
            self.orders_filled.append(order)
            print(f"  >> Tick {current_tick}: ORDER FILLED - {order.action.value} @ {order.avg_fill_price:.2f}")


def create_test_data():
    """Create test market data."""
    base_time = datetime.now()
    candles = []
    
    # Candle 1: Price = 100
    candles.append(Candle(
        symbol="TEST",
        exchange="TEST", 
        timestamp=base_time,
        open=100.0,
        high=102.0,
        low=98.0,
        close=100.0,
        volume=1000
    ))
    
    # Candle 2: Price drops to 94 (should trigger buy order at 95)
    candles.append(Candle(
        symbol="TEST",
        exchange="TEST",
        timestamp=base_time + timedelta(minutes=1),
        open=100.0,
        high=100.0,
        low=94.0,
        close=94.0,
        volume=1000
    ))
    
    # Candle 3: Price rises to 106 (should trigger sell order at 105)
    candles.append(Candle(
        symbol="TEST", 
        exchange="TEST",
        timestamp=base_time + timedelta(minutes=2),
        open=94.0,
        high=106.0,
        low=94.0,
        close=106.0,
        volume=1000
    ))
    
    return candles


def main():
    print("Testing Tick-Based Order Execution System...")
    print("=" * 60)
    
    # Create minimal configuration with all required fields
    config = AppConfig(
        openalgo=OpenAlgoConfig(api_key="test"),
        data=DataConfig(
            symbol="TEST", 
            exchange="TEST",
            start="2023-01-01",
            end="2023-01-02"
        ),
        backtest=BacktestConfig(
            initial_cash=10000.0,
            commission_per_trade=1.0,
            fee_bps=5.0,
            slippage_bps=2.0
        ),
        strategy=StrategyConfig(),
        ui=UIConfig(),
        logging=LoggingConfig()
    )
    
    # Create backtest engine
    engine = BacktestEngine(config)
    
    # Create and set strategy
    strategy = TestStrategy()
    strategy.initialize()
    engine.set_strategy(strategy)
    
    # Create test data
    market_data = create_test_data()
    
    print(f"Running backtest with {len(market_data)} ticks (candles)...")
    print("-" * 60)
    
    # Run backtest
    result = engine.run_backtest(market_data)
    
    # Analyze results
    print("\n" + "=" * 60)
    print("TICK SYSTEM RESULTS:")
    print("-" * 60)
    print(f"Total ticks processed: {engine.processed_ticks}")
    print(f"Orders submitted: {len(strategy.orders_submitted)}")
    print(f"Orders filled: {len(strategy.orders_filled)}")
    
    print("\nTick Data Summary:")
    for tick_data in strategy.tick_data:
        print(f"  Tick {tick_data['tick']}: Price={tick_data['price']:.2f}, Active Orders={tick_data['active_orders']}")
    
    print("\nSubmitted Orders:")
    for order in strategy.orders_submitted:
        print(f"  {order.action.value} @ {order.price:.2f} - Final Status: {order.status.value}")
    
    print("\nFilled Orders:")
    for order in strategy.orders_filled:
        print(f"  {order.action.value} @ {order.avg_fill_price:.2f}")
    
    # Verify tick system worked correctly
    success = True
    
    # Check that ticks were processed correctly
    if engine.processed_ticks != len(market_data):
        print(f"\nFAIL: Expected {len(market_data)} ticks, processed {engine.processed_ticks}")
        success = False
    
    # Check that orders were processed in different ticks
    if len(strategy.orders_filled) > 0:
        for order in strategy.orders_filled:
            if order.filled_at == market_data[0].timestamp:
                print(f"\nFAIL: Order was filled in the same tick it was submitted!")
                success = False
    
    # Verify we have tick data for each candle
    if len(strategy.tick_data) != len(market_data):
        print(f"\nFAIL: Expected {len(market_data)} tick records, got {len(strategy.tick_data)}")
        success = False
    
    if success:
        print("\nSUCCESS: Tick system is working correctly!")
        print("- Orders are processed on each tick")
        print("- Orders wait for proper price triggers")
        print("- Tick tracking is accurate")
    else:
        print("\nFAIL: Tick system test failed")
    
    return success


if __name__ == "__main__":
    main()