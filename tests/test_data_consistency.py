#!/usr/bin/env python3
"""
Test script to verify that chart data and trade data are consistent.
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


class DataConsistencyTestStrategy(BaseStrategy):
    """Test strategy to verify chart and trade data consistency."""
    
    def __init__(self):
        super().__init__("DataConsistencyTestStrategy")
        self.candle_count = 0
        self.orders_submitted = []
        self.orders_filled = []
    
    def initialize(self, **kwargs):
        self._initialized = True
    
    def on_bar(self, candle: Candle):
        self.candle_count += 1
        current_tick = self.context.get_current_tick() if self.context else 0
        
        # Submit orders at specific price levels to test execution timing
        if current_tick == 1:
            print(f"Tick {current_tick}: Price = {candle.close:.2f} - Placing test orders")
            
            # Limit buy order below market
            buy_order = Order(
                id=str(uuid.uuid4()),
                symbol="TEST",
                exchange="TEST",
                action=OrderAction.BUY,
                order_type=OrderType.LIMIT,
                quantity=100,
                price=candle.close - 2.0  # 2 points below
            )
            
            # Limit sell order above market
            sell_order = Order(
                id=str(uuid.uuid4()),
                symbol="TEST",
                exchange="TEST", 
                action=OrderAction.SELL,
                order_type=OrderType.LIMIT,
                quantity=50,
                price=candle.close + 2.0  # 2 points above
            )
            
            self.submit_order(buy_order)
            self.submit_order(sell_order)
            self.orders_submitted.extend([buy_order, sell_order])
            
            print(f"  Submitted BUY limit @ {buy_order.price:.2f}")
            print(f"  Submitted SELL limit @ {sell_order.price:.2f}")
        
        elif current_tick <= 5:
            print(f"Tick {current_tick}: Price = {candle.close:.2f}")
    
    def on_order_update(self, order: Order):
        if order.status == OrderStatus.FILLED:
            self.orders_filled.append(order)
            current_tick = self.context.get_current_tick() if self.context else 0
            print(f"  >> Tick {current_tick}: {order.action.value} order filled @ {order.avg_fill_price:.2f}")


def create_test_candles():
    """Create test candles that will trigger the limit orders."""
    base_time = datetime.now()
    candles = []
    
    # Candle 1: Base price 100
    candles.append(Candle(
        symbol="TEST",
        exchange="TEST",
        timestamp=base_time,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1000
    ))
    
    # Candle 2: Price drops to trigger buy order (low hits 98)
    candles.append(Candle(
        symbol="TEST",
        exchange="TEST",
        timestamp=base_time + timedelta(minutes=1),
        open=100.0,
        high=100.0,
        low=98.0,  # This should trigger buy order at 98
        close=99.0,
        volume=1000
    ))
    
    # Candle 3: Price rises to trigger sell order (high hits 102)
    candles.append(Candle(
        symbol="TEST",
        exchange="TEST",
        timestamp=base_time + timedelta(minutes=2),
        open=99.0,
        high=102.0,  # This should trigger sell order at 102
        low=99.0,
        close=101.0,
        volume=1000
    ))
    
    return candles


def test_data_consistency():
    """Test that chart and trade data are consistent."""
    print("Testing Chart and Trade Data Consistency...")
    print("=" * 60)
    
    # Create configuration
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
    strategy = DataConsistencyTestStrategy()
    strategy.initialize()
    engine.set_strategy(strategy)
    
    # Create test data
    candles = create_test_candles()
    
    print(f"Input candles:")
    for i, candle in enumerate(candles, 1):
        print(f"  Candle {i}: {candle.timestamp.strftime('%H:%M:%S')} - OHLC({candle.open:.1f}, {candle.high:.1f}, {candle.low:.1f}, {candle.close:.1f})")
    
    print("-" * 60)
    
    # Run backtest
    result = engine.run_backtest(candles)
    
    # Analyze consistency
    print("\n" + "=" * 60)
    print("DATA CONSISTENCY ANALYSIS:")
    print("-" * 60)
    
    print(f"Input candles: {len(candles)}")
    print(f"Orders submitted: {len(strategy.orders_submitted)}")
    print(f"Orders filled: {len(strategy.orders_filled)}")
    print(f"Trade records: {len(result.trades)}")
    
    # Verify that each filled order has a corresponding trade record
    print("\nOrder Execution vs Trade Record Consistency:")
    for filled_order in strategy.orders_filled:
        # Find corresponding trade record
        matching_trade = None
        for trade in result.trades:
            if trade.id == filled_order.id:
                matching_trade = trade
                break
        
        if matching_trade:
            print(f"✓ Order {filled_order.action.value} @ {filled_order.avg_fill_price:.2f} -> Trade {matching_trade.side} @ {matching_trade.entry_price:.2f}")
            
            # Verify data consistency
            if abs(filled_order.avg_fill_price - matching_trade.entry_price) > 0.01:
                print(f"  ❌ Price mismatch: Order {filled_order.avg_fill_price:.2f} vs Trade {matching_trade.entry_price:.2f}")
                return False
            
            if filled_order.filled_at != matching_trade.entry_time:
                print(f"  ❌ Time mismatch: Order {filled_order.filled_at} vs Trade {matching_trade.entry_time}")
                return False
        else:
            print(f"❌ No trade record found for filled order: {filled_order.action.value} @ {filled_order.avg_fill_price:.2f}")
            return False
    
    # Verify timing consistency with candles
    print("\nTiming Consistency with Candle Data:")
    for trade in result.trades:
        # Find which candle this trade should correspond to
        trade_time = trade.entry_time
        corresponding_candle = None
        for candle in candles:
            if candle.timestamp <= trade_time:
                corresponding_candle = candle
        
        if corresponding_candle:
            print(f"✓ Trade {trade.side} @ {trade.entry_price:.2f} occurred during candle with range [{corresponding_candle.low:.1f}-{corresponding_candle.high:.1f}]")
            
            # Verify price is within candle range
            if not (corresponding_candle.low <= trade.entry_price <= corresponding_candle.high):
                print(f"  ❌ Trade price {trade.entry_price:.2f} outside candle range [{corresponding_candle.low:.1f}-{corresponding_candle.high:.1f}]")
                return False
        else:
            print(f"❌ Could not find corresponding candle for trade at {trade_time}")
            return False
    
    print("\n✅ ALL CONSISTENCY CHECKS PASSED!")
    print("- Order execution data matches trade records")
    print("- Timestamps are consistent")
    print("- Prices are within expected candle ranges")
    print("- Trade data accurately reflects what happened in the chart")
    
    return True


if __name__ == "__main__":
    success = test_data_consistency()
    if success:
        print(f"\n🎉 Data consistency test PASSED!")
    else:
        print(f"\n❌ Data consistency test FAILED!")