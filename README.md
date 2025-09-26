# Grid Trading Backtesting Engine

A production-ready backtesting framework for trading strategies with OpenAlgo integration, featuring your existing grid trading bot and comprehensive web UI.

## Features

- **Event-driven backtesting engine** with realistic order simulation
- **Grid trading strategy integration** using your existing `grid_trading_bot.py`
- **OpenAlgo API integration** with synthetic data fallback
- **Web dashboard** for configuration, execution, and visualization
- **Comprehensive metrics** (Sharpe, Sortino, max drawdown, etc.)
- **CLI tools** for headless execution
- **Data caching** for performance
- **Docker support** for easy deployment

## Quick Start

### 1. Installation

```bash
# Clone and setup
git clone <repository>
cd backtest-engine

# Install dependencies
pip install -r requirements.txt

# Or use make
make dev
```

### 2. Configuration

Copy and customize the configuration:

```bash
cp config.yaml my-config.yaml
# Edit my-config.yaml with your settings
```

**Key configurations:**
- Set `OPENALGO_API_KEY` environment variable or use synthetic data
- Configure strategy parameters in `strategy` section
- Adjust risk parameters in `backtest` section

### 3. Quick Verification

Test the setup with our included test script:

```bash
# Test OpenAlgo integration (no API key needed for structure test)
python test_openalgo.py

# Expected output:
# ✅ Provider initialized with client: <class 'openalgo.api'>
# ✅ Available exchanges: ['NSE', 'BSE', 'MCX', 'NCDEX']
# ✅ OpenAlgo provider integration SUCCESSFUL!
```

### 4. Run Backtest (CLI)

```bash
# Run with synthetic data (no API key required)
python -m scripts.backtest --config config.yaml --output results/

# Run with OpenAlgo data  
OPENALGO_API_KEY="your-key" python -m scripts.backtest --config config.yaml

# Verbose output
python -m scripts.backtest --config config.yaml --verbose
```

### 5. Web Dashboard

```bash
# Start web interface
make web

# Or directly:
python -m app.api.main

# Access at http://localhost:8000
```

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
2. Open http://localhost:8000
3. Configure backtest parameters
4. Run backtest and view results
5. Download reports (CSV/JSON)

### Custom Strategy

Your `grid_trading_bot.py` is wrapped via `GridStrategyAdapter`:

```python
from app.strategies import GridStrategyAdapter

strategy = GridStrategyAdapter()
strategy.initialize(
    grid_levels=10,
    grid_spacing_pct=1.0,
    order_amount=1000
)
```

## Configuration

### Environment Variables

```bash
export OPENALGO_API_KEY="your-api-key"
export OPENALGO_BASE_URL="http://127.0.0.1:5000"
```

### config.yaml Structure

```yaml
openalgo:
  api_key: "${OPENALGO_API_KEY}"
  base_url: "http://127.0.0.1:5000"

data:
  exchange: "NSE"
  symbol: "RELIANCE"
  timeframe: "1h"
  start: "2023-01-01"
  end: "2023-12-31"
  use_synthetic: true  # Fallback to synthetic data

backtest:
  initial_cash: 100000
  fee_bps: 5
  slippage_bps: 2

strategy:
  type: "grid"
  grid_levels: 10
  grid_spacing_pct: 1.0
  order_amount: 1000
  grid_type: "arithmetic"
```

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

## Metrics & Analysis

The engine calculates comprehensive metrics:

**Return Metrics:**
- Total return (absolute & percentage)
- Annualized return
- CAGR

**Risk Metrics:**
- Maximum drawdown
- Volatility
- Sharpe ratio
- Sortino ratio
- Calmar ratio

**Trading Metrics:**
- Total trades
- Win rate
- Profit factor
- Average trade P&L
- Consecutive wins/losses

## Development

### Running Tests

```bash
make test
# Or: pytest tests/
```

### Code Quality

```bash
make lint    # Run ruff linting
make format  # Run black formatting
```

### Docker

```bash
make docker-build
make docker-run

# Or directly:
docker build -t grid-backtest .
docker run -p 8000:8000 -e OPENALGO_API_KEY=your-key grid-backtest
```

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

### 🚧 **In Progress**


### 📋 **Upcoming Features**

**Strategy Enhancements:**
- [ ] Multi-asset grid trading
- [ ] Dynamic grid adjustment
- [ ] Risk management integration
- [ ] Parameter optimization

**Advanced Analytics:**
- [ ] Portfolio attribution analysis
- [ ] Risk decomposition
- [ ] Monte Carlo simulations
- [ ] Walk-forward analysis

**Production Features:**
- [ ] Live trading simulation
- [ ] Alert system integration
- [ ] Database persistence
- [ ] API rate limiting

## Support

For issues and questions:
1. Check configuration in `config.yaml`
2. Review logs in `backtest.log`
3. Test with synthetic data first
4. Verify OpenAlgo connection

## License

MIT License - see LICENSE file for details.
