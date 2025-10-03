# Quick Start Guide: Universal Strategy Adapter

## 🎯 Overview

The Universal Strategy Adapter eliminates ~80% of boilerplate code when adding new trading strategies. Instead of writing 100-500 lines of adapter code for each strategy, you can now add strategies with **zero adapter code**.

---

## 🚀 Quick Start

### Adding a New Strategy (5 Minutes)

#### Step 1: Implement Your Trading Bot

Create your bot by extending `TradingBot` base class:

```python
# strats/my_new_bot.py
from strats.trading_bot import TradingBot

class MyNewTradingBot(TradingBot):
    def __init__(self, api_key, host, symbol, exchange, 
                 my_param1=10, my_param2=2.0, **kwargs):
        self.client = api(api_key, host)
        self.symbol = symbol
        self.exchange = exchange
        self.my_param1 = my_param1
        self.my_param2 = my_param2
        # ... your initialization
    
    def run_backtest(self, current_price):
        """
        🔑 KEY METHOD - Execute ONE bar of strategy logic.
        No loops! No sleeps! Just the logic for a single candle.
        """
        # Check filled orders
        self.check_filled_orders()
        
        # Your strategy logic here
        # Example: Simple moving average crossover
        if self.should_buy(current_price):
            self.place_market_order('buy', self.calculate_quantity(current_price))
        elif self.should_sell(current_price):
            self.place_market_order('sell', self.get_position())
    
    # Implement other required TradingBot methods...
    def place_market_order(self, action, quantity):
        # ... implementation
        
    def check_filled_orders(self):
        # ... implementation
    
    # ... etc
```

#### Step 2: Register Your Strategy

Add one line to `app/strategies/registry.py`:

```python
def auto_register_strategies():
    from strats.grid_trading_bot import GridTradingBot
    from strats.supertrend_trading_bot import SupertrendTradingBot
    from strats.my_new_bot import MyNewTradingBot  # ← Add this
    
    StrategyRegistry.register('grid', GridTradingBot)
    StrategyRegistry.register('supertrend', SupertrendTradingBot, 
                             SupertrendStrategyAdapter)
    StrategyRegistry.register('mynew', MyNewTradingBot)  # ← Add this
```

#### Step 3: Use It!

```yaml
# config.yaml
strategy:
  type: mynew  # ← Your new strategy
  my_param1: 20
  my_param2: 3.5
```

**That's it!** Your strategy is now fully integrated with the backtesting system.

---

## 📝 Configuration

### Basic Configuration (No Buffer)

```yaml
strategy:
  type: mynew
  symbol: RELIANCE
  exchange: NSE
  # Your custom parameters
  my_param1: 20
  my_param2: 3.5
  buffer_enabled: false
```

### With Historical Buffer (For Indicators)

```yaml
strategy:
  type: mynew
  symbol: RELIANCE
  exchange: NSE
  # Your custom parameters  
  my_param1: 20
  my_param2: 3.5
  # Buffer configuration
  buffer_enabled: true
  buffer_days: 90
  buffer_mode: skip_initial  # or 'use_incomplete'
```

**Buffer Modes:**
- `skip_initial`: Wait for 90 days of data before trading
- `use_incomplete`: Start trading with whatever data is available

---

## 🔧 Advanced Usage

### Using Hooks for Customization

If you need light customization without a full custom adapter:

```python
from app.strategies import StrategyRegistry, hooks

# Get strategy
strategy = StrategyRegistry.get('mynew')

# Add hooks
strategy.pre_bar_hook = hooks.StrategyHooks.risk_management_check
strategy.post_bar_hook = hooks.StrategyHooks.log_performance

# Or chain multiple hooks
strategy.pre_bar_hook = hooks.chain_hooks(
    hooks.StrategyHooks.update_indicators,
    hooks.StrategyHooks.risk_management_check
)

# Initialize
strategy.initialize(**config)
```

### Accessing Historical Data

If your strategy needs historical data:

```python
class MyNewTradingBot(TradingBot):
    def run_backtest(self, current_price):
        # Access the adapter's historical buffer
        # (Must have buffer_enabled=true in config)
        historical_df = self.historical_data  # pandas DataFrame
        
        if historical_df is not None and len(historical_df) >= 20:
            # Calculate indicators using historical data
            sma_20 = historical_df['close'].tail(20).mean()
            # ... your logic
```

The universal adapter automatically maintains this buffer for you!

---

## 🎨 Custom Adapter (Complex Strategies)

When you need a custom adapter (rare):

### When to Use Custom Adapter

✅ **Use Custom Adapter when:**
- Heavy DataFrame preprocessing needed
- Complex multi-timeframe analysis
- Custom order flow that doesn't fit standard pattern
- Specialized state synchronization

❌ **Use Universal Adapter when:**
- Standard single-bar execution
- Bot manages its own indicators
- Straightforward order flow
- 80% of strategies fall into this category

### Creating Custom Adapter

```python
# app/strategies/my_custom_adapter.py
from .base_strategy import BaseStrategy

class MyCustomAdapter(BaseStrategy):
    def __init__(self):
        super().__init__("MyCustomAdapter")
        # ... custom initialization
    
    def initialize(self, **params):
        # Custom initialization logic
        pass
    
    def on_bar(self, candle):
        # Custom bar processing
        pass
```

Register with custom adapter:

```python
StrategyRegistry.register('mynew', MyNewTradingBot, MyCustomAdapter)
```

---

## 📊 Examples

### Example 1: Simple RSI Strategy

```python
class RSITradingBot(TradingBot):
    def __init__(self, api_key, host, symbol, exchange, 
                 rsi_period=14, rsi_oversold=30, rsi_overbought=70):
        self.client = api(api_key, host)
        self.symbol = symbol
        self.exchange = exchange
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.price_history = []
        self.position = 0
    
    def run_backtest(self, current_price):
        # Update price history
        self.price_history.append(current_price)
        
        # Need enough data for RSI
        if len(self.price_history) < self.rsi_period + 1:
            return
        
        # Calculate RSI
        rsi = self.calculate_rsi(self.price_history[-self.rsi_period-1:])
        
        # Trading logic
        if self.position == 0 and rsi < self.rsi_oversold:
            # Buy signal
            quantity = self.calculate_quantity(current_price)
            self.place_market_order('buy', quantity)
        elif self.position > 0 and rsi > self.rsi_overbought:
            # Sell signal
            self.place_market_order('sell', self.position)
```

**Usage:**
```python
StrategyRegistry.register('rsi', RSITradingBot)
```

```yaml
strategy:
  type: rsi
  rsi_period: 14
  rsi_oversold: 30
  rsi_overbought: 70
```

### Example 2: MACD Strategy with Buffer

```python
class MACDTradingBot(TradingBot):
    def __init__(self, api_key, host, symbol, exchange,
                 fast_period=12, slow_period=26, signal_period=9):
        self.client = api(api_key, host)
        self.symbol = symbol
        self.exchange = exchange
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.position = 0
    
    def run_backtest(self, current_price):
        # Get historical data from universal adapter's buffer
        # (Set buffer_enabled=true, buffer_days=90 in config)
        if not hasattr(self, 'adapter_historical_data'):
            return
        
        df = self.adapter_historical_data
        
        # Need enough data for MACD
        if len(df) < self.slow_period + self.signal_period:
            return
        
        # Calculate MACD
        macd, signal, histogram = self.calculate_macd(df)
        
        # Trading logic
        if self.position == 0 and histogram > 0:
            # Buy signal
            quantity = self.calculate_quantity(current_price)
            self.place_market_order('buy', quantity)
        elif self.position > 0 and histogram < 0:
            # Sell signal
            self.place_market_order('sell', self.position)
```

**Usage:**
```python
StrategyRegistry.register('macd', MACDTradingBot)
```

```yaml
strategy:
  type: macd
  fast_period: 12
  slow_period: 26
  signal_period: 9
  buffer_enabled: true
  buffer_days: 90
  buffer_mode: skip_initial
```

---

## 🐛 Troubleshooting

### Issue: "Strategy not found"

```python
# Check registered strategies
from app.strategies import StrategyRegistry
print(StrategyRegistry.list_strategies())
```

### Issue: Parameters not being passed

The universal adapter uses introspection to map parameters. Ensure your bot's `__init__` parameter names match your config:

```python
# ✅ Good - parameter names match
def __init__(self, api_key, host, symbol, exchange, my_param=10):
    # Config can use: my_param: 20
    
# ❌ Bad - parameter name doesn't match
def __init__(self, api_key, host, symbol, exchange, param=10):
    # Config uses: my_param: 20 ← Won't work!
```

### Issue: Buffer not available

Make sure `buffer_enabled: true` in config and access it correctly:

```python
def run_backtest(self, current_price):
    # ❌ Wrong - looking for self.historical_data
    if self.historical_data:  # Won't work
        ...
    
    # ✅ Correct - access through adapter
    if hasattr(self, 'adapter_historical_data'):
        df = self.adapter_historical_data
        ...
```

---

## 📚 API Reference

### StrategyRegistry

```python
# Register strategy (universal adapter)
StrategyRegistry.register(name: str, bot_class: Type[TradingBot])

# Register strategy (custom adapter)
StrategyRegistry.register(name: str, bot_class: Type[TradingBot],
                         adapter_class: Type[BaseStrategy])

# Get strategy instance
strategy = StrategyRegistry.get(name: str) -> BaseStrategy

# List all registered strategies
strategies = StrategyRegistry.list_strategies() -> Dict[str, str]

# Check if strategy exists
exists = StrategyRegistry.is_registered(name: str) -> bool
```

### UniversalStrategyAdapter

```python
# Initialize
adapter = UniversalStrategyAdapter(bot_class, strategy_name=None)

# Configure
adapter.initialize(
    symbol='RELIANCE',
    exchange='NSE',
    buffer_enabled=False,
    buffer_days=90,
    buffer_mode='skip_initial',
    **bot_specific_params
)

# Set hooks
adapter.setup_hook = my_setup_function
adapter.pre_bar_hook = my_pre_bar_function
adapter.post_bar_hook = my_post_bar_function
adapter.first_bar_hook = my_first_bar_function

# Get historical data
df = adapter.get_historical_data()  # Returns pandas DataFrame

# Get state
state = adapter.get_state()  # Returns dict with adapter state
```

### TradingBot Interface

```python
class YourBot(TradingBot):
    # Required methods
    def run_backtest(self, current_price: float) -> None:
        """Execute ONE bar of strategy logic"""
        
    def run_strategy(self) -> None:
        """Execute live trading (with loops/sleeps)"""
        
    def place_market_order(self, action: str, quantity: int) -> Dict:
        """Place a market order"""
        
    def place_limit_order(self, action: str, quantity: int, price: float) -> Dict:
        """Place a limit order"""
        
    def cancel_all_orders(self) -> List[str]:
        """Cancel all pending orders"""
        
    def check_filled_orders(self) -> List[Dict]:
        """Check for filled orders"""
        
    def save_state(self) -> None:
        """Save bot state to file"""
        
    def load_state(self) -> None:
        """Load bot state from file"""
        
    def get_current_price(self) -> float:
        """Get current market price"""
        
    def get_performance_summary(self) -> Dict:
        """Get performance metrics"""
        
    def get_trading_data_for_export(self) -> Dict:
        """Get data for export/dashboard"""
        
    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L"""
```

---

## ✅ Checklist for New Strategy

- [ ] Created bot class extending `TradingBot`
- [ ] Implemented `run_backtest(current_price)` method
- [ ] Implemented all required `TradingBot` methods
- [ ] Registered strategy in `registry.py`
- [ ] Added configuration in `config.yaml`
- [ ] Tested with test script
- [ ] Documented any special requirements

---

## 🎓 Best Practices

1. **Keep `run_backtest` Simple**: One bar, no loops, no sleeps
2. **Use Buffer for Indicators**: Enable buffer if you need historical data
3. **Match Parameter Names**: Config keys should match `__init__` parameters
4. **Handle Edge Cases**: Check for None/empty data
5. **Log Appropriately**: Use `self.logger` for debugging
6. **Test Incrementally**: Test each component separately
7. **Document Custom Logic**: Add comments for complex calculations

---

## 📞 Support

For issues or questions:
1. Check this guide
2. Review `UNIVERSAL_ADAPTER_SUMMARY.md`
3. Look at existing implementations (`GridTradingBot`, `SupertrendTradingBot`)
4. Check test files (`test_universal_adapter.py`)

---

**Happy Trading! 🚀**
