# Grid Trading Bot for OpenAlgo Platform

A sophisticated Python-based grid trading system that automates buy and sell orders at predetermined price levels, designed to profit from market volatility within a defined range.

## 🆕 New Feature: Initial Position Strategy

**Important Update:** The bot now includes an `initial_position_strategy` option to control how sell orders are handled when you have no shares in stock:

- **`wait_for_buy`** (Default): Conservative approach - only places sell orders after buy orders are filled
- **`buy_at_market`**: Aggressive approach - buys shares at market price immediately to enable all sell orders

See [INITIAL_POSITION_STRATEGY_GUIDE.md](INITIAL_POSITION_STRATEGY_GUIDE.md) for detailed information.

## 📈 What is Grid Trading?

Grid trading is an algorithmic trading strategy that:
- Places multiple buy orders below the current market price
- Places multiple sell orders above the current market price  
- Creates a "grid" of orders at regular intervals
- Profits from price oscillations by buying low and selling high
- Works best in ranging/sideways markets
- Can be adapted for trending markets with auto-reset features

## 🔧 System Architecture

### Core Components

1. **GridTradingBot Class** - Main trading engine
2. **Order Management** - Handles order placement and tracking
3. **Risk Management** - Stop-loss, take-profit, and position limits
4. **State Persistence** - Saves/restores bot state across sessions
5. **Performance Tracking** - Real-time P&L and statistics
6. **Breakout Handling** - Automatic grid reset on price breakouts

### Grid Types

#### Arithmetic Grid
- Fixed price intervals between levels
- Example: ₹100, ₹101, ₹102, ₹103, ₹104
- Best for stocks with stable price ranges

#### Geometric Grid  
- Percentage-based intervals
- Example: ₹100, ₹101.5, ₹103.02, ₹104.57
- Better for volatile stocks or different price ranges

## 🚀 Quick Start Guide

### Prerequisites

1. **OpenAlgo Platform** running on localhost:5000
2. **Python 3.7+** with required packages
3. **Broker account** connected to OpenAlgo
4. **Sufficient capital** for grid orders

### Installation

```bash
# Install dependencies
pip install openalgo pandas numpy

# Download the bot files
# - grid_trading_bot.py
# - configs/active/grid_config.json  
# - run_grid_bot.py
```

### Configuration

Edit `configs/active/grid_config.json` with your settings:

```json
{
  "api_settings": {
    "api_key": "your-actual-api-key"
  },
  "trading_settings": {
    "symbol": "RELIANCE",
    "exchange": "NSE"
  },
  "grid_configuration": {
    "grid_levels": 5,
    "grid_spacing_pct": 1.5,
    "order_amount": 1000
  }
}
```

### Running the Bot

```bash
# Interactive launcher (recommended)
python run_grid_bot.py

# Direct execution
python grid_trading_bot.py
```

## 📊 Strategy Parameters

### Grid Configuration

| Parameter | Description | Recommended Range |
|-----------|-------------|------------------|
| `grid_levels` | Orders above/below center | 3-10 |
| `grid_spacing_pct` | % between grid levels | 0.5-3.0% |
| `order_amount` | ₹ per grid order | 500-5000 |
| `grid_type` | arithmetic/geometric | arithmetic for most stocks |

### Risk Management

| Parameter | Description | Recommended Value |
|-----------|-------------|------------------|
| `stop_loss_pct` | % loss from center | 5-15% |
| `take_profit_pct` | % profit from center | 10-25% |
| `auto_reset` | Reset grid on breakout | true |

## 💡 Strategy Logic

### Grid Setup Process

1. **Determine Center Price** - Current market price or user-defined
2. **Calculate Grid Levels** - Based on spacing and number of levels
3. **Place Buy Orders** - Below center price at calculated intervals
4. **Place Sell Orders** - Above center price at calculated intervals
5. **Set Risk Bounds** - Stop-loss and take-profit levels

### Order Execution Flow

```
Price Movement → Order Filled → Place Opposite Order → Update P&L
     ↓
Check Bounds → Within Grid? → Continue
     ↓              ↓
   Breakout → Reset Grid (if auto_reset enabled)
```

### Example Grid Setup

For RELIANCE at ₹2500 with 5 levels and 1% spacing:

**Buy Orders (below center):**
- ₹2475.00 (1% below)
- ₹2450.25 (2% below)  
- ₹2425.75 (3% below)
- ₹2401.50 (4% below)
- ₹2377.49 (5% below)

**Sell Orders (above center):**
- ₹2525.00 (1% above)
- ₹2550.25 (2% above)
- ₹2575.75 (3% above)
- ₹2601.50 (4% above)
- ₹2627.49 (5% above)

## ⚡ Advanced Features

### Automatic Grid Reset

When price breaks outside grid bounds:
1. Cancel all pending orders
2. Calculate current position P&L
3. Reset grid around new price level
4. Resume trading with updated parameters

### Position Management

- **Long Bias**: More buy orders filled = long position
- **Short Bias**: More sell orders filled = short position  
- **Hedging**: Automatic opposite order placement
- **Risk Control**: Position limits and exposure management

### State Persistence

The bot saves its state to JSON file including:
- Current grid configuration
- Active orders and positions
- Trade history and P&L
- Performance metrics

## 📈 Performance Monitoring

### Key Metrics

- **Total Trades**: Number of completed buy/sell cycles
- **Win Rate**: Percentage of profitable trades
- **Realized P&L**: Profit from closed positions
- **Unrealized P&L**: Current position value
- **Grid Efficiency**: Orders filled vs. total orders
- **Drawdown**: Maximum loss from peak

### Logging and Alerts

The bot provides comprehensive logging:
- Order placement and fills
- Grid resets and breakouts  
- P&L updates and statistics
- Error handling and recovery
- Performance summaries

## ⚠️ Risk Considerations

### Market Risks

1. **Trending Markets**: Grid can suffer in strong trends
2. **Gap Risk**: Large price gaps can skip grid levels
3. **Volatility Risk**: High volatility may trigger frequent resets
4. **Liquidity Risk**: Low liquidity can affect order execution

### Configuration Risks

1. **Over-leveraging**: Too many orders or large amounts
2. **Tight Grids**: Frequent small trades increase costs
3. **Wide Grids**: Miss opportunities in ranging markets
4. **No Stop Loss**: Unlimited downside risk

### Best Practices

✅ **Start Small**: Begin with small order amounts and few levels
✅ **Test First**: Use paper trading or simulation mode
✅ **Monitor Actively**: Check bot status regularly
✅ **Proper Sizing**: Risk only 1-2% of capital per grid level
✅ **Market Selection**: Choose liquid, ranging stocks
✅ **Time Management**: Avoid major news events and earnings

## 🔧 Troubleshooting

### Common Issues

**"Connection Error"**
- Verify OpenAlgo platform is running
- Check API key is correct and active
- Ensure network connectivity

**"Insufficient Funds"**
- Check account balance
- Reduce order amounts or grid levels
- Verify margin requirements

**"Order Rejected"**  
- Check symbol and exchange names
- Verify trading permissions
- Ensure minimum order value requirements

**"Grid Not Profitable"**
- Review market conditions (trending vs ranging)
- Adjust grid spacing or levels
- Consider different symbols or timeframes

### Debug Mode

Enable detailed logging by modifying the bot:
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

## 📊 Performance Optimization

### Parameter Tuning

1. **Backtest Different Settings**: Test various grid configurations
2. **Market Analysis**: Study symbol's price behavior and volatility
3. **Optimize Spacing**: Balance between frequency and profitability
4. **Risk-Reward Ratio**: Ensure favorable risk-adjusted returns

### Advanced Configurations

```python
# Multiple symbol grids
symbols = ['RELIANCE', 'TCS', 'INFY']
bots = [GridTradingBot(symbol=sym, **config) for sym in symbols]

# Dynamic grid sizing based on volatility
volatility = calculate_volatility(price_history)
spacing = base_spacing * volatility_multiplier
```

## 🎯 Strategy Variations

### Conservative Grid
- Fewer levels (3-5)
- Wider spacing (2-3%)
- Lower position sizes
- Strict stop-losses

### Aggressive Grid  
- More levels (8-12)
- Tighter spacing (0.5-1%)
- Larger position sizes
- Wider stop-losses

### Trend-Following Grid
- Asymmetric grids (more orders in trend direction)
- Dynamic spacing based on momentum
- Trailing stop-losses
- Breakout continuation strategy

## 📚 Additional Resources

### Learning Materials
- Grid trading theory and mathematics
- Risk management principles  
- Market microstructure concepts
- Algorithmic trading best practices

### Tools and Libraries
- OpenAlgo API documentation
- pandas for data analysis
- numpy for mathematical calculations
- matplotlib for visualization

## 🛡️ Disclaimer

**IMPORTANT**: This software is for educational and informational purposes only. Grid trading involves substantial risk of loss and is not suitable for all investors. Past performance does not guarantee future results.

**Risk Warning**: 
- You can lose money using this bot
- Start with small amounts you can afford to lose
- Understand the strategy before using real money
- Monitor the bot's performance regularly
- Consider consulting a financial advisor

The authors are not responsible for any financial losses incurred from using this software.

---

## 📞 Support

For technical support and questions:
1. Check the log files for error details
2. Verify OpenAlgo platform is functioning
3. Review configuration parameters
4. Test with small amounts first
5. Join trading communities for strategy discussions

**Happy Grid Trading! 🎯**
