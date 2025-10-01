# Grid Trading Bot Web Dashboard

A modern web-based interface for monitoring and controlling your grid trading bot with real-time charts, TradingView integration, and comprehensive analytics.

## 🌟 Features

### 📊 Real-time Visualization
- **Live Price Charts**: Interactive price charts showing current market data
- **Grid Level Visualization**: Visual representation of all grid levels and active orders
- **Performance Charts**: Track your P&L over time with detailed analytics
- **Order Visualization**: See all orders (filled and pending) with timestamps and details

### 🎮 Interactive Controls
- **Real-time Monitoring**: Start/stop live monitoring with WebSocket updates
- **Bot Status**: Monitor bot health and configuration
- **Order Management**: View active and filled orders in real-time
- **Performance Metrics**: Live P&L, position tracking, and trade statistics

### 📈 Advanced Analytics
- **TradingView Integration**: Professional-grade charting capabilities
- **Grid Analysis**: Detailed breakdown of grid utilization and effectiveness
- **Risk Metrics**: Monitor exposure, position size, and risk parameters
- **Historical Performance**: Track trading performance over time

## 🚀 Quick Start

### Option 1: Windows Batch File (Recommended)
```batch
# Double-click to run
launch_web_dashboard.bat
```

### Option 2: Python Launch Script
```bash
python launch_trading_bot.py
```

### Option 3: Direct Web Dashboard
```bash
python web_dashboard.py
```

## 🔧 Installation

### Prerequisites
- Python 3.7+
- OpenAlgo platform running (default: http://127.0.0.1:5000)
- Valid `grid_config.json` configuration file

### Install Dependencies
```bash
pip install -r requirements.txt
```

### New Web Dependencies
The following packages are required for the web dashboard:
- `flask>=2.0.0` - Web framework
- `flask-cors>=3.0.0` - Cross-origin resource sharing  
- `flask-socketio>=5.0.0` - Real-time communication
- `eventlet>=0.33.0` - Async server for SocketIO

## 🖥️ Web Dashboard Interface

### Main Dashboard Components

#### 1. **Summary Metrics Row**
- Total P&L with color-coded indicators
- Current market price
- Current position size
- Total number of trades executed
- Active orders count
- Unrealized P&L

#### 2. **Price Chart**
- Real-time price updates
- Grid level overlays
- Historical price data (last 500 data points)
- Interactive zoom and pan

#### 3. **Performance Chart**
- Cumulative P&L over time
- Individual trade markers
- Performance trend analysis

#### 4. **Grid Levels Panel**
- Visual representation of all grid levels
- Color-coded by order type (Buy/Sell/Center)
- Active order indicators
- Distance from current price

#### 5. **Bot Status Panel**
- Trading symbol and exchange
- Grid configuration details
- Bot active/inactive status
- Grid type and spacing information

#### 6. **Orders Table**
- Recent orders (last 20 transactions)
- Real-time order status updates
- Detailed order information
- Filterable by order type and status

### 🎨 Dashboard Features

#### Real-time Updates
- **WebSocket Connection**: Live updates without page refresh
- **Price Streaming**: Real-time price data from your OpenAlgo platform
- **Order Notifications**: Instant alerts when orders are filled
- **Status Monitoring**: Live bot health and connection status

#### Interactive Charts
- **Chart.js Integration**: Smooth, responsive charts
- **Time-based X-axis**: Automatic time formatting
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Dark Theme**: Easy on the eyes for long monitoring sessions

#### Professional UI
- **Bootstrap 5**: Modern, responsive design
- **Dark Theme**: Professional trading interface
- **Color-coded Metrics**: Green for profits, red for losses
- **Status Indicators**: Visual connection and bot status indicators

## 🔗 API Endpoints

The web dashboard provides several REST API endpoints:

### Summary Data
- `GET /api/summary` - Bot performance summary
- `GET /api/price-history` - Historical price data
- `GET /api/orders` - Order history and active orders
- `GET /api/grid-levels` - Current grid level configuration
- `GET /api/performance-chart` - Performance timeline data

### Controls
- `POST /api/start-monitoring` - Start real-time monitoring
- `POST /api/stop-monitoring` - Stop real-time monitoring

### WebSocket Events
- `price_update` - Real-time price updates
- `summary_update` - Bot summary updates
- `orders_filled` - New order fill notifications

## 📱 Access Your Dashboard

Once launched, your dashboard will be available at:
```
http://localhost:5001
```

The dashboard automatically opens in your default browser when using the launcher script.

## 🛠️ Configuration

The web dashboard uses your existing `grid_config.json` configuration file. No additional configuration is required.

### Sample Grid Config
```json
{
  "api_settings": {
    "api_key": "your-openalgo-api-key",
    "host": "http://127.0.0.1:5000"
  },
  "trading_settings": {
    "symbol": "IDFCFIRSTB",
    "exchange": "NSE"
  },
  "grid_configuration": {
    "grid_levels": 7,
    "grid_spacing_pct": 1.5,
    "grid_type": "geometric",
    "order_amount": 500
  }
}
```

## 🚨 Safety Features

### Risk Management Integration
- **Stop Loss Monitoring**: Visual indicators for stop loss levels
- **Position Size Tracking**: Real-time position value monitoring
- **Grid Utilization**: Monitor how much of your grid is active
- **Connection Status**: Clear indicators of platform connectivity

### Data Security
- **Local Operation**: All data stays on your machine
- **No External Dependencies**: Works entirely with your OpenAlgo platform
- **State Persistence**: Maintains trading state across restarts

## 🎯 Trading Workflow

1. **Configure** your bot using `grid_config.json`
2. **Launch** the web dashboard using the launcher script
3. **Monitor** real-time price action and grid performance
4. **Control** the bot using web interface or CLI
5. **Analyze** performance using built-in charts and metrics

## 🔍 Troubleshooting

### Common Issues

**Web Dashboard Won't Start**
```bash
pip install flask flask-cors flask-socketio eventlet
```

**No Price Data**
- Check OpenAlgo platform is running
- Verify API key in `grid_config.json`
- Ensure trading symbol is correct

**Charts Not Loading**
- Check browser console for JavaScript errors
- Ensure internet connection for CDN resources
- Try refreshing the page

**WebSocket Connection Issues**
- Check firewall settings for port 5001
- Verify no other services using port 5001
- Try restarting the dashboard

## 📊 Screenshots

The dashboard provides:
- 📈 Professional dark-themed interface
- 🎯 Real-time price charts with grid overlays
- 💰 Performance tracking and P&L visualization
- ⚡ Grid level monitoring with active order indicators
- 📋 Comprehensive order history and status tracking

## 🔮 Future Enhancements

Planned features for future releases:
- Advanced charting with technical indicators
- Export functionality for trading data
- Email/SMS notifications for important events
- Multiple bot instance management
- Advanced backtesting interface
- Portfolio-level analytics

## 📞 Support

For issues specific to the web dashboard:
1. Check the console output for error messages
2. Verify all dependencies are installed correctly
3. Ensure your `grid_config.json` is valid
4. Check that OpenAlgo platform is accessible

## 📄 License

This web dashboard is part of the Grid Trading Bot project and follows the same license terms as the main bot.
