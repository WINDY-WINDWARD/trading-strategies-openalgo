# Grid Trading Backtesting Engine

A comprehensive, production-ready backtesting framework for grid trading strategies with OpenAlgo integration, featuring advanced analytics, web dashboards, and extensive customization options.

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
```yaml
strategy:
  grid_levels: 10              # Number of levels per side (20 total orders)
  grid_spacing_pct: 1.5        # Spacing between grid levels
  order_amount: 1000           # Rupees per grid order
  grid_type: geometric         # arithmetic/geometric
  initial_position_strategy: wait_for_buy
  stop_loss_pct: 8.0           # Risk management
  take_profit_pct: 12.0
  auto_reset: true             # Automatic grid repositioning
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


## Extending the Framework

### Custom Strategies

1. Inherit from `BaseStrategy`
2. Implement `on_bar()` method
3. Register with backtest engine

### Custom Data Providers

1. Implement data provider interface
2. Add caching support
3. Handle errors and rate limiting

### Custom Metrics

1. Extend `MetricsCalculator`
2. Add new metric calculations
3. Update result models


#### **Custom Strategies**
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

#### **Custom Data Providers**
```python
from app.data.base_provider import BaseDataProvider

class CustomDataProvider(BaseDataProvider):
    def fetch_historical_data(self, symbol, start, end):
        # Implement custom data fetching
        return self.process_data(raw_data)
```

#### **Custom Metrics**
```python
from app.core.metrics import MetricsCalculator

class CustomMetricsCalculator(MetricsCalculator):
    def calculate_custom_metric(self, trades):
        # Implement specialized metrics
        return custom_analysis
```

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
git clone <repository>
cd grid-trading-backtest
pip install -r requirements.txt
```

### 2. Configuration

```bash
cp example-config.yaml config.yaml
# Edit with your parameters
```
**Key configurations:**
- Set `OPENALGO_API_KEY` environment variable or use synthetic data
- Configure strategy parameters in `strategy` section
- Adjust risk parameters in `backtest` section

### 2.5. Quick Verification

Test the setup with our included test script:

```bash
# Test OpenAlgo integration (no API key needed for structure test)
python test_openalgo.py

# Expected output:
# ✅ Provider initialized with client: <class 'openalgo.api'>
# ✅ Available exchanges: ['NSE', 'BSE', 'MCX', 'NCDEX']
# ✅ OpenAlgo provider integration SUCCESSFUL!
```


### 3. Run Backtest

```bash
# CLI execution
python -m scripts.backtest --config config.yaml

# Web interface
make web
# Visit http://localhost:42069
```

### 4. Analyze Results

- View comprehensive performance metrics
- Export detailed trade logs
- Tune parameters and re-run

### 5. Live Trading
```bash
# uses grid_config.json
# Web interface
make live
# Visit http://localhost:5001 (check printed URL)
```

## Architecture Overview

```
grid-trading-backtest/
├── 🤖 GridTradingBot/          # Core trading strategy
├── 📊 BacktestEngine/          # Event-driven simulation
├── 🌐 WebDashboard/           # Interactive UI
├── 📈 Analytics/              # Performance metrics
├── 💾 DataProviders/          # Market data sources
├── ⚙️ Configuration/          # Parameter management
├── 🛠️ CLITools/              # Automation scripts
└── 🐳 Deployment/            # Docker & cloud support
```

This framework provides everything needed for professional-grade grid trading strategy development, testing, and deployment.


## Project Structure

```
backtest-engine/
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
│   │   └── grid_strategy_adapter.py # Grid bot adapter
│   ├── models/              # Data models
│   │   ├── config.py           # Configuration models
│   │   ├── market_data.py      # Market data models
│   │   ├── orders.py           # Order models
│   │   └── results.py          # Results models
│   ├── api/                 # Web API
│   │   ├── main.py            # FastAPI application
│   │   └── routes/            # API endpoints
│   ├── ui/                  # Web UI
│   │   ├── templates/         # Jinja2 templates
│   │   └── static/            # CSS/JS assets
│   └── utils/               # Utilities
│       ├── config_loader.py   # Configuration management
│       ├── logging_config.py  # Logging setup
│       └── time_helpers.py    # Time utilities
├── scripts/                 # CLI scripts
│   ├── backtest.py           # Run backtest
│   ├── fetch_data.py         # Fetch market data
│   └── report.py             # Generate reports
├── tests/                   # Test suite
├── grid_trading_bot.py      # Your original bot (unchanged)
├── config.yaml              # Main configuration
├── requirements.txt         # Dependencies
├── Dockerfile              # Docker container
├── Makefile                # Build automation
└── README.md               # This file
```

## Usage Examples

### CLI Backtest

```bash
# Basic backtest with synthetic data
python -m scripts.backtest --config config.yaml

# With custom date range (edit config.yaml):
data:
  start: "2023-01-01"
  end: "2023-12-31"
  symbol: "RELIANCE"

# Save results
python -m scripts.backtest --config config.yaml --output ./results
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
- ✅ Docker containerization setup

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

**Web Interface:**
- ✅ FastAPI endpoints for configuration and execution
- ✅ HTML templates for dashboard UI
- ✅ Real-time progress updates
- ✅ Chart visualizations with Plotly

**Strategy Implementation:**
- ✅ Grid trading bot with dynamic grid levels
- ✅ Initial position strategies
- ✅ Stop-loss and take-profit management
- ✅ Automatic grid reset on breakout

### 📋 **Upcoming Features**

**Strategy Enhancements:**
- [ ] Multi-asset grid trading


## Debugging

For issues and questions:
1. Check configuration in `config.yaml` set logging to DEBUG
2. Review logs in `backtest.log`
3. Test with synthetic data first
4. Verify OpenAlgo connection

