# Trading Backtesting Engine with OpenAlgo Integration for Live Market Data and trading

A comprehensive, production-ready backtesting framework for grid trading strategies with OpenAlgo integration, featuring advanced analytics, web dashboards, and extensive customization options.

## ⚠️ IMPORTANT DISCLAIMER

**⚠️ NO LIABILITY - USE AT YOUR OWN RISK**

This software is provided "AS IS" without warranty of any kind. The author(s) assume **NO LIABILITY** for any financial losses, damages, or consequences resulting from the use of this trading software. By using this software, you acknowledge and accept that:

- **Trading involves substantial risk** of loss and is not suitable for all investors
- **Past performance does not guarantee future results**
- **This software is for educational and research purposes only**
- **You are solely responsible** for your trading decisions and outcomes
- **The author(s) are not liable** for any direct, indirect, incidental, or consequential damages
- **No warranty or guarantee** is provided regarding accuracy, reliability, or profitability

**USE THIS SOFTWARE AT YOUR OWN RISK AND DISCRETION.**

## 🚀 Key Features

### 🤖 **Advanced Grid Trading Bot**
- **Dynamic Grid Creation**: Arithmetic (fixed spacing) and geometric (percentage-based) grid types
- **Flexible Grid Levels**: Configurable number of buy/sell levels (up to 20+ levels per side)
- **Smart Position Management**: Three initial position strategies:
  - `wait_for_buy`: Places sell orders only after acquiring shares through buy orders
  - `buy_at_market`: Buys initial shares at market price to cover all sell orders
  - Custom position-based allocation
- **Risk Management**: Stop-loss and take-profit boundaries with automatic grid reset
- **Breakout Handling**: Automatic grid repositioning when price breaks boundaries
- **State Persistence**: Saves/loads trading state for continuity across sessions
- **Real-time Monitoring**: Comprehensive logging and performance tracking

### 📊 **Professional Backtesting Engine**
- **Event-Driven Architecture**: Realistic order execution simulation with market/limit orders
- **Multi-Timeframe Support**: 1m, 5m, 15m, 30m, 1h, 1d intervals
- **Portfolio Management**: Position tracking, cash management, margin handling
- **Order Simulation**: Realistic slippage, market impact, and fill probability modeling
- **Tax Calculation**: Automatic delivery (0.1%) and intraday (0.025%) tax computation
- **Performance Attribution**: Trade-by-trade P&L analysis with entry/exit tracking

### 🎯 **Comprehensive Analytics & Metrics**

#### **Return Metrics**
- Total return (absolute & percentage)
- Annualized return and CAGR
- Risk-adjusted returns (Sharpe)
- Maximum drawdown and recovery analysis

#### **Risk Metrics**
- Value at Risk (VaR) estimates

#### **Trading Metrics**
- Win rate and profit factor analysis
- Average trade P&L and holding periods
- Consecutive wins/losses tracking
- Trade frequency and timing analysis

#### **Tax & Cost Analysis**
- Delivery vs intraday trade classification
- Tax payable calculations with position tracking
- Transaction cost analysis (fees, slippage)
- After-tax performance metrics

### 🌐 **Interactive Web Dashboard**
- **Real-time Backtesting**: Live progress updates with WebSocket connections
- **Interactive Charts**: TradingView-style price charts with grid level overlays
- **Performance Visualization**: Equity curves, drawdown charts, trade distributions
- **Grid Monitoring**: Live grid levels, order status, position tracking
- **Parameter Tuning**: Dynamic strategy configuration without code changes
- **Export Capabilities**: CSV/JSON results download, PDF reports
- **Historical Analysis**: Trade-by-trade breakdown with P&L attribution

### 📈 **Data Sources & Integration**

#### **OpenAlgo Integration**
- **Official API Support**: Full integration with OpenAlgo Python package
- **Live Market Data**: Real-time and historical data from NSE, BSE, MCX, NCDEX
- **Rate Limiting**: Intelligent request throttling and error handling
- **Authentication**: Secure API key management with environment variables
- **Data Validation**: Comprehensive error handling and fallback mechanisms

#### **Synthetic Data Generator**
- **Realistic Price Movements**: Geometric Brownian motion with configurable volatility
- **Market Regimes**: Bull, bear, and sideways market simulation
- **Volume Modeling**: Realistic volume patterns and spreads
- **Custom Scenarios**: Trend, mean-reversion, and volatility clustering
- **Reproducible Testing**: Seeded random generation for consistent results

#### **Data Caching System**
- **SQLite Backend**: High-performance local data storage
- **Automatic Cache Management**: TTL-based expiration and size limits
- **Parquet/JSON Formats**: Efficient storage and fast retrieval
- **Offline Mode**: Complete functionality without internet connection

### ⚙️ **Configuration & Customization**

#### **Strategy Parameters**

**Grid Trading Strategy:**
```yaml
strategy:
  type: grid                   # Strategy type
  grid_levels: 10              # Number of levels per side (20 total orders)
  grid_spacing_pct: 1.5        # Spacing between grid levels
  order_amount: 1000           # Rupees per grid order
  grid_type: geometric         # arithmetic/geometric
  initial_position_strategy: wait_for_buy
  stop_loss_pct: 8.0           # Risk management
  take_profit_pct: 12.0
  auto_reset: true             # Automatic grid repositioning
```

**Supertrend Strategy:**
```yaml
strategy:
  type: supertrend             # Strategy type
  atr_period: 10               # ATR calculation period
  atr_multiplier: 3.0          # Supertrend sensitivity
  max_order_amount: 5000.0    # Maximum rupees per trade
  stop_loss_pct: 3.0           # Risk management
  take_profit_pct: 5.0
  # Buffer configuration for accurate Supertrend calculation
  buffer_enabled: true         # Enable data buffer
  buffer_days: 90              # Buffer period in days
  buffer_mode: skip_initial    # Buffer handling mode
```

#### **Buffer Configuration for Supertrend Strategy**

The Supertrend strategy requires historical data for accurate ATR (Average True Range) calculations. To ensure reliable signals, the buffer system provides two modes:

**Buffer Parameters:**
- `buffer_enabled`: Enable/disable the buffer system (default: true)
- `buffer_days`: Number of days to use as buffer (default: 90)
- `buffer_mode`: How to handle the buffer period
  - `skip_initial`: Skip trading during the first N bars/days to allow accurate calculations
  - `fetch_additional`: Fetch additional historical data before the backtest period (future feature)

**Buffer Modes Explained:**

1. **skip_initial mode** (Recommended):
   - Processes the first 90 days (or specified buffer_days) of data without trading
   - Allows Supertrend indicator to stabilize with accurate ATR calculations
   - Trading begins only after the buffer period is complete
   - More realistic as it avoids early signals based on insufficient data

2. **fetch_additional mode** (Future enhancement):
   - Would fetch additional historical data before the backtest start date
   - Backtest would begin immediately with pre-warmed indicators
   - Currently equivalent to skip_initial mode

**Example Buffer Calculation:**
- For 1h timeframe with 90-day buffer: 90 × 24 = 2,160 bars skipped
- For 15m timeframe with 90-day buffer: 90 × 96 = 8,640 bars skipped
- For 1d timeframe with 90-day buffer: 90 × 1 = 90 bars skipped

**Configuration Examples:**
```yaml
# Conservative approach - 90 day buffer
strategy:
  buffer_enabled: true
  buffer_days: 90
  buffer_mode: skip_initial

# Faster testing - 30 day buffer
strategy:
  buffer_enabled: true
  buffer_days: 30
  buffer_mode: skip_initial

# Disable buffer (not recommended for production)
strategy:
  buffer_enabled: false
```

#### **Position Sizing for Supertrend Strategy**

The Supertrend strategy supports intelligent position sizing based on available capital and maximum order amount:

**Key Parameters:**
- `max_order_amount`: Maximum amount in rupees to spend per trade (default: 50,000)
- The bot calculates optimal share quantity based on current stock price

**Position Sizing Logic:**
```
shares_to_buy = max_order_amount / current_stock_price
quantity = max(1, floor(shares_to_buy))  # At least 1 share
```

**Example:**
- Stock price: ₹100
- max_order_amount: ₹50,000
- Shares purchased: 500 shares
- Total investment: ₹50,000

**Configuration Examples:**
```yaml
# Conservative position sizing
strategy:
  max_order_amount: 25000.0    # ₹25,000 per trade

# Aggressive position sizing
strategy:
  max_order_amount: 100000.0   # ₹1,00,000 per trade

# Small position sizing for testing
strategy:
  max_order_amount: 5000.0     # ₹5,000 per trade
```

#### **Backtest Configuration**
```yaml
backtest:
  initial_cash: 100000         # Starting capital
  fee_bps: 5                   # Transaction fees (basis points)
  slippage_bps: 2              # Price slippage simulation
  tax_delivery_pct: 0.1        # Delivery tax rate
  tax_intraday_pct: 0.025      # Intraday tax rate
```

#### **Data Configuration**
```yaml
data:
  exchange: NSE
  symbol: RELIANCE
  timeframe: 1h
  start: "2023-01-01"
  end: "2023-12-31"
  use_synthetic: false         # Fallback to synthetic data
  cache_max_age_hours: 24
```

### 🔧 **Extensibility & Development**

#### **🚀 Universal Strategy Adapter System**

**New approach to adding new trading strategies with less code!**

The Universal Strategy Adapter eliminates the need for writing 100-500 lines of boilerplate adapter code for each new trading strategy. Simply implement your trading logic in a `TradingBot` class and register it - no custom adapter needed!

**Key Features:**
- ✅ **Zero Boilerplate**: New strategies require 0 adapter lines (vs 100-500 previously)
- ✅ **Automatic Parameter Mapping**: Uses introspection to wire parameters
- ✅ **Universal Buffer System**: Built-in 90-day buffer for indicator warm-up
- ✅ **Lifecycle Hooks**: Customization points without writing full adapters
- ✅ **Standard & Custom Support**: Use universal for simple strategies, custom for complex ones

**Quick Example:**
```python
# 1. Implement your strategy (in strats/my_bot.py)
class MyTradingBot(TradingBot):
    def __init__(self, api_key, symbol, my_param, **kwargs):
        super().__init__(api_key, symbol, **kwargs)
        self.my_param = my_param
    
    def run_backtest(self, current_price):
        # Your strategy logic here
        if self.should_buy(current_price):
            self.place_order('BUY', 100, current_price)

# 2. Register it (in app/strategies/registry.py)
StrategyRegistry.register('mystrategy', MyTradingBot)

# 3. Done! Use it immediately in config:
strategy:
  type: mystrategy
  my_param: 42
```

**When to Use Universal vs Custom:**
- **Universal Adapter**: Simple strategies (RSI, MACD, Grid, Moving Average Cross)
- **Custom Adapter**: Complex multi-timeframe analysis, heavy DataFrame operations

📚 **Learn More**: See [UNIVERSAL_ADAPTER_SUMMARY.md](docs/UNIVERSAL_ADAPTER_SUMMARY.md) for detailed documentation, examples, and implementation guide.

---

## Extending the Framework

### Custom Strategies

#### **Simple Strategies (Universal Adapter)**
```python
from strats.trading_bot import TradingBot
from app.strategies.registry import StrategyRegistry

# 1. Create your bot class
class RSITradingBot(TradingBot):
    def __init__(self, api_key, symbol, rsi_period=14, **kwargs):
        super().__init__(api_key, symbol, **kwargs)
        self.rsi_period = rsi_period
    
    def run_backtest(self, current_price):
        # Calculate RSI and trade
        rsi = self.calculate_rsi()
        if rsi < 30:  # Oversold
            self.place_order('BUY', 100, current_price)
        elif rsi > 70:  # Overbought
            self.place_order('SELL', 100, current_price)

# 2. Register (uses UniversalStrategyAdapter automatically)
StrategyRegistry.register('rsi', RSITradingBot)

# That's it! Zero adapter code needed.
```

#### **Complex Strategies (Custom Adapter)**
```python
from app.strategies.base_strategy import BaseStrategy

class CustomStrategy(BaseStrategy):
    def on_bar(self, candle):
        # Implement your trading logic
        if self.should_buy(candle):
            self.submit_order(Order(
                action=OrderAction.BUY,
                quantity=100,
                price=candle.close
            ))
```

### Custom Data Providers

1. Implement data provider interface
2. Add caching support
3. Handle errors and rate limiting

#### **Custom Data Providers**
```python
from app.data.base_provider import BaseDataProvider

class CustomDataProvider(BaseDataProvider):
    def fetch_historical_data(self, symbol, start, end):
        # Implement custom data fetching
        return self.process_data(raw_data)
```

### Custom Metrics
```python
from app.core.metrics import MetricsCalculator

class CustomMetricsCalculator(MetricsCalculator):
    def calculate_custom_metric(self, trades):
        # Implement specialized metrics
        return custom_analysis
```

---

## 📚 Documentation

Comprehensive guides to help you get started and master the platform:

### Strategy Guides
- **[Grid Trading Guide](docs/GRID_TRADING_GUIDE.md)** - Complete guide to grid trading strategy, configuration, and best practices
- **[Initial Position Strategy Guide](docs/INITIAL_POSITION_STRATEGY_GUIDE.md)** - Understanding `wait_for_buy` vs `buy_at_market` position strategies
- **[Universal Strategy Adapter](docs/UNIVERSAL_ADAPTER_SUMMARY.md)** - Add new strategies with 80% less code using the universal adapter system

### Platform Documentation
- **[Web Dashboard Guide](docs/WEB_DASHBOARD_README.md)** - Interactive web interface for monitoring and controlling your trading bots
- **[Quick Start Guide](docs/QUICK_START_GUIDE.md)** - Get up and running in minutes
- **[New Strategy Documentation Setup](docs/NEW_STRATEGY_DOCUMENTATION_SETUP.md)** - Checklist for adding a new strategy and documenting it end-to-end

### Additional Resources
- **[README](README.md)** - This file - comprehensive overview of all features
- **[License](LICENSE)** - MIT License details

---

### 📊 **Advanced Features**

#### **Live Trading Bridge**
- Paper trading simulation
- Live execution with OpenAlgo
- Risk management integration

### 🎯 **Use Cases & Applications**

#### **Strategy Development**
- Grid strategy optimization and parameter tuning
- Comparative analysis of different grid configurations
- Risk management strategy validation

#### **Portfolio Management**
- Asset allocation optimization

#### **Risk Analysis**
- Stress testing under various market conditions
- Scenario analysis for black swan events
- Risk-adjusted performance evaluation

#### **Educational Tools**
- Interactive trading strategy visualization
- Performance metrics explanation
- Market mechanics simulation

### 📈 **Performance & Scalability**

- **High-Performance Processing**: Handles 100K+ candles efficiently
- **Memory Optimized**: Streaming data processing for large datasets
- **Concurrent Execution**: Multi-strategy parallel backtesting
- **Database Integration**: SQLite support for caching

### 🔒 **Security & Reliability**

- **API Key Protection**: Environment variable management
- **Data Validation**: Comprehensive input sanitization
- **Error Handling**: Graceful failure recovery
- **Logging**: Structured logging with multiple levels


---

## Quick Start

### 1. Installation

```bash
git clone https://github.com/WINDY-WINDWARD/trading-strategies-openalgo.git
cd trading-strategies-openalgo
pip install -r requirements.txt
```

### 2. Configuration

```bash
cp configs/templates/example-config.yaml configs/active/config.yaml
# Shared settings live in config.yaml
```

Per-strategy overrides live in:

```bash
configs/active/config-grid.yaml
configs/active/config-supertrend.yaml
```

At runtime, strategy config is loaded and merged over `configs/active/config.yaml` (base), so shared keys like `openalgo`, `ui`, and `logging` can stay in `config.yaml`.

The web configuration editor strategy dropdown is driven by:

```bash
configs/active/strats.yaml
```

Default user-visible strategies are `grid` and `supertrend`.

**Key configurations:**
- Set `OPENALGO_API_KEY` environment variable or use synthetic data
- Keep shared defaults in `configs/active/config.yaml`
- Keep strategy-specific settings in each strategy YAML file
- Control strategy visibility in UI using `configs/active/strats.yaml`

### 2.5. Quick Verification

Test the setup with our included test script:

```bash
# Test OpenAlgo integration (no API key needed for structure test)
python tests/test_openalgo.py

# Expected output:
# ✅ Provider initialized with client: <class 'openalgo.api'>
# ✅ Available exchanges: ['NSE', 'BSE', 'MCX', 'NCDEX']
# ✅ OpenAlgo provider integration SUCCESSFUL!
```


### 3. Run Backtest

```bash
# CLI execution
python -m scripts.backtest --config configs/active/config.yaml

# Web interface
make web
# Visit http://localhost:42069

# Optional: force web startup strategy
WEB_STRATEGY=supertrend make web
```

### 4. Analyze Results

- View comprehensive performance metrics
- Export detailed trade logs
- Tune parameters and re-run

### 5. Live Trading
```bash
# uses configs/active/grid_config.json
# Web interface
make live
# Visit http://localhost:5001 (check printed URL)
```

## Architecture Overview

```
trading-strategies-openalgo/
├── 🤖 GridTradingBot/          # Core trading strategy
├── 🤖 SupertrendBot/           # Supertrend trading strategy  
├── 📊 BacktestEngine/          # Event-driven simulation
├── 🌐 WebDashboard/           # Interactive UI
├── 📈 Analytics/              # Performance metrics
├── 💾 DataProviders/          # Market data sources
├── ⚙️ Configuration/          # Parameter management
└── 🛠️ CLITools/              # Automation scripts
```

This framework provides everything needed for professional-grade grid trading strategy development, testing, and deployment.


## Project Structure

```
trading-strategies-openalgo/
├── app/
│   ├── core/                 # Core backtesting engine
│   │   ├── backtest_engine.py   # Main engine
│   │   ├── portfolio.py         # Portfolio management  
│   │   ├── order_simulator.py   # Order execution simulation
│   │   ├── metrics.py           # Performance metrics
│   │   └── events.py            # Event system
│   ├── data/                 # Data providers
│   │   ├── openalgo_provider.py # OpenAlgo integration
│   │   ├── synthetic_data.py    # Synthetic data generator
│   │   └── cache_manager.py     # Data caching
│   ├── strategies/           # Strategy adapters
│   │   ├── base_strategy.py     # Strategy interface
│   │   ├── grid_strategy_adapter.py # Grid bot adapter
│   │   ├── supertrend_strategy_adapter.py # Supertrend bot adapter
│   │   └── mock_openalgo_client.py # Common mock client
│   ├── models/              # Data models
│   │   ├── config.py           # Configuration models
│   │   ├── market_data.py      # Market data models
│   │   ├── orders.py           # Order models
│   │   └── results.py          # Results models
│   ├── api/                 # Web API
│   │   ├── main.py            # FastAPI application
│   │   └── routes/            # API endpoints
│   ├── ui/                  # Web UI
│   │   └── templates/         # Jinja2 templates
│   └── utils/               # Utilities
│       ├── config_loader.py   # Configuration management
│       ├── logging_config.py  # Logging setup
│       └── time_helpers.py    # Time utilities
├── scripts/                 # CLI scripts
│   ├── backtest.py           # Run backtest
│   └── launch_web.py         # Launch web dashboard
├── strats/                  # Trading strategy implementations
│   ├── grid_trading_bot.py   # Grid trading strategy
│   ├── supertrend_trading_bot.py # Supertrend strategy
│   └── trading_bot.py        # Base trading bot
├── tests/                   # Test suite
│   ├── test_openalgo.py      # OpenAlgo integration tests
│   ├── test_strategy.py      # Strategy tests
│   └── ...                  # Other test files
├── templates/               # Web dashboard templates
│   ├── Griddashboard.html    # Grid trading dashboard
│   └── SupertrendDashboard.html # Supertrend dashboard
├── docs/                    # Documentation
│   ├── GRID_TRADING_GUIDE.md
│   ├── NEW_STRATEGY_DOCUMENTATION_SETUP.md
│   └── WEB_DASHBOARD_README.md
├── configs/
│   ├── active/
│   │   ├── config.yaml              # Shared/base configuration
│   │   ├── config-grid.yaml         # Grid strategy overrides
│   │   ├── config-supertrend.yaml   # Supertrend strategy overrides
│   │   ├── strats.yaml              # UI strategy catalog (dropdown + config path)
│   │   ├── grid_config.json         # Grid strategy config
│   │   └── supertrend_config.json   # Supertrend strategy config
│   └── templates/
│       └── example-config.yaml      # Backtest config template
├── requirements.txt         # Dependencies
├── Makefile                # Build automation
├── LICENSE                 # MIT License
└── README.md               # This file
```

## Usage Examples

### CLI Backtest

```bash
# Basic backtest with synthetic data
python -m scripts.backtest --config configs/active/config.yaml

# With custom date range (edit configs/active/config.yaml):
data:
  start: "2023-01-01"
  end: "2023-12-31"
  symbol: "RELIANCE"

# Run backtest and analyze results
python -m scripts.backtest --config configs/active/config.yaml
```

### Web Interface

1. Start server: `make web`
2. Open http://localhost:42069
3. Configure backtest parameters
4. Run backtest and view results
5. Download reports (CSV/JSON)

## Data Sources

### Synthetic Data (Default)
- Realistic price movements using geometric Brownian motion
- Configurable volatility and trends
- No API key required
- Perfect for testing and development

### OpenAlgo Integration
- Live historical data from exchanges
- Automatic caching for performance
- Rate limiting and error handling
- ✅ **Complete OpenAlgo integration** with official Python package
- ✅ **API parameters mapped** (`start_date`, `end_date`, intervals)
- ✅ **Response parsing** handles multiple field formats


## Development Status & Roadmap

### ✅ **Completed Components**

**Core Engine:**
- ✅ Event-driven backtesting architecture
- ✅ Portfolio management with position tracking
- ✅ Realistic order simulation (market/limit orders)
- ✅ Comprehensive performance metrics
- ✅ Configuration system with environment variables
- ✅ CLI backtest execution script
- ✅ Makefile for build automation

**Data Integration:**
- ✅ **OpenAlgo provider** using official Python package (`openalgo.api`)
- ✅ **API authentication** and error handling (tested with 403 responses)
- ✅ **Parameter mapping** (`start_date`, `end_date`, `interval` formats)
- ✅ **Response parsing** with flexible field handling
- ✅ **Connection testing** validated against OpenAlgo server
- ✅ **Synthetic data generator** for testing without API
- ✅ **Data caching** with Parquet/JSON storage

**Strategy Framework:**
- ✅ Base strategy interface
- ✅ Event-driven strategy pattern
- ✅ Grid strategy adapter
- ✅ Supertrend strategy adapter

**Web Interface:**
- ✅ FastAPI endpoints for configuration and execution
- ✅ HTML templates for dashboard UI
- ✅ Real-time progress updates
- ✅ Chart visualizations with Plotly

**Strategy Implementation:**
- ✅ Grid trading bot with dynamic grid levels
- ✅ Supertrend trading bot with ATR-based signals
- ✅ Initial position strategies
- ✅ Stop-loss and take-profit management
- ✅ Automatic grid reset on breakout

### 📋 **Upcoming Features**

**Strategy Enhancements:**
- [ ] Multi-asset grid trading


## Debugging

For issues and questions:
1. Check shared config in `configs/active/config.yaml` and strategy overrides in `configs/active/config-grid.yaml` / `configs/active/config-supertrend.yaml`
2. Review logs in `backtest.log`
3. Test with synthetic data first
4. Verify OpenAlgo connection

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### MIT License Summary

- ✅ **Free to use** - Commercial and personal use permitted
- ✅ **Free to modify** - Can be modified and distributed
- ✅ **Free to distribute** - Can be shared and redistributed
- ❌ **No warranty** - Software provided "as is" without warranties
- ❌ **No liability** - Authors not liable for any damages

**Key Points:**
- The software is provided **"AS IS"** without warranty of any kind
- Authors are **NOT LIABLE** for any damages or losses
- Use at your **OWN RISK** and responsibility

For the full license text, see the [LICENSE](LICENSE) file in the project root.

