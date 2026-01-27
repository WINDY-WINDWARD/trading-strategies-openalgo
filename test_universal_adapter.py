# Test the universal adapter with Grid strategy
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from app.strategies import StrategyRegistry
from app.models.market_data import Candle
from datetime import datetime

print("=" * 60)
print("Testing Universal Strategy Adapter")
print("=" * 60)

# Check registry
print("\n1. Registry Status:")
strategies = StrategyRegistry.list_strategies()
for name, adapter_type in strategies.items():
    print(f"   {name}: {adapter_type}")

# Test Grid with Universal
print("\n2. Testing Grid Strategy (Universal Adapter):")
try:
    strategy = StrategyRegistry.get('grid')
    print(f"   ✓ Created: {strategy.name}")
    print(f"   ✓ Type: {type(strategy).__name__}")
    
    # Initialize
    strategy.initialize(
        symbol='IDBI',
        exchange='NSE',
        grid_levels=5,
        grid_spacing_pct=1.0,
        order_amount=1000,
        grid_type='geometric',
        stop_loss_pct=5.0,
        take_profit_pct=10.0,
        auto_reset=True,
        initial_position_strategy='wait_for_buy',
        buffer_enabled=False
    )
    print(f"   ✓ Initialized successfully")
    print(f"   ✓ Bot class: {type(strategy.bot).__name__}")
    print(f"   ✓ Buffer enabled: {strategy.buffer_enabled}")
    
    # Process a test candle
    test_candle = Candle(
        symbol='IDBI',
        exchange='NSE',
        timestamp=datetime.now(),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=10000
    )
    
    # Mock context for order submission
    class MockContext:
        def __init__(self):
            self.orders = []
        def submit_order(self, order):
            self.orders.append(order)
            return True
    
    strategy.set_context(MockContext())
    strategy.on_bar(test_candle)
    print(f"   ✓ Processed test candle at price: {test_candle.close}")
    
    print("\n✅ Grid Strategy (Universal Adapter) - PASSED")
    
except Exception as e:
    print(f"\n❌ Grid Strategy (Universal Adapter) - FAILED")
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()

# Test Supertrend with Custom
print("\n3. Testing Supertrend Strategy (Custom Adapter):")
try:
    strategy = StrategyRegistry.get('supertrend')
    print(f"   ✓ Created: {strategy.name}")
    print(f"   ✓ Type: {type(strategy).__name__}")
    
    print("\n✅ Supertrend Strategy (Custom Adapter) - PASSED")
    
except Exception as e:
    print(f"\n❌ Supertrend Strategy (Custom Adapter) - FAILED")
    print(f"   Error: {e}")

print("\n" + "=" * 60)
print("Test Complete!")
print("=" * 60)
