#!/usr/bin/env python3
"""
Grid Trading Bot Web Dashboard

A Flask-based web interface for monitoring and visualizing the grid trading bot
with TradingView charts integration, real-time updates, and comprehensive analytics.
"""

from flask import Flask, render_template, jsonify, request
from flask import Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List
import os
import csv

from strats.grid_trading_bot import GridTradingBot

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global bot instance
bot = None
monitoring_thread = None
monitoring_active = False
trading_thread = None
trading_active = False

def load_bot_config():
    """Load configuration and initialize bot"""
    global bot
    try:
        with open('grid_config.json', 'r') as f:
            config = json.load(f)
        
        api_key = config['api_settings']['api_key']
        host = config['api_settings']['host']
        symbol = config['trading_settings']['symbol']
        exchange = config['trading_settings']['exchange']
        
        bot = GridTradingBot(
            api_key=api_key,
            host=host,
            symbol=symbol,
            exchange=exchange,
            grid_levels=config['grid_configuration']['grid_levels'],
            grid_spacing_pct=config['grid_configuration']['grid_spacing_pct'],
            order_amount=config['grid_configuration']['order_amount'],
            grid_type=config['grid_configuration']['grid_type'],
            stop_loss_pct=config['risk_management']['stop_loss_pct'],
            take_profit_pct=config['risk_management']['take_profit_pct'],
            auto_reset=config['risk_management']['auto_reset'],
            state_file=config['execution_settings']['state_file'],
            initial_position_strategy=config['execution_settings'].get('initial_position_strategy', 'wait_for_buy')
        )
        
        # Load existing state if available
        bot.load_state()
        return True
        
    except Exception as e:
        print(f"Error loading bot config: {e}")
        return False

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('Griddashboard.html')

@app.route('/api/summary')
def get_summary():
    """Get bot performance summary"""
    if not bot:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    try:
        summary = bot.get_performance_summary()
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trading-status')
def get_trading_status():
    """Get current trading status"""
    if not bot:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    return jsonify({
        'trading_active': trading_active,
        'bot_active': bot.is_active,
        'monitoring_active': monitoring_active,
        'grid_setup': bot.grid_center_price is not None,
        'grid_center_price': bot.grid_center_price,
        'pending_orders': len(bot.pending_orders),
        'current_position': bot.current_position
    })

@app.route('/api/price-history')
def get_price_history():
    """Get price history for chart"""
    if not bot:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    try:
        # Get price history from bot
        price_data = []
        for entry in bot.price_history[-500:]:  # Last 500 data points
            price_data.append({
                'timestamp': entry['timestamp'].isoformat(),
                'price': entry['price']
            })
        
        return jsonify(price_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders')
def get_orders():
    """Get order history and active orders"""
    if not bot:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    try:
        # Filled orders
        filled_orders = []
        for order in bot.filled_orders:
            filled_orders.append({
                'id': order.get('order_id', 'N/A'),
                'symbol': bot.symbol,
                'type': order['type'],
                'quantity': order['quantity'],
                'fill_price': order['fill_price'],
                'timestamp': order['timestamp'].isoformat() if hasattr(order['timestamp'], 'isoformat') else order['timestamp'],
                'status': 'FILLED'
            })
        
        # Active orders
        active_orders = []
        
        # Buy orders
        for price, order_id in bot.buy_orders.items():
            if order_id in bot.pending_orders:
                order_details = bot.pending_orders[order_id]
                active_orders.append({
                    'id': order_id,
                    'symbol': bot.symbol,
                    'type': 'BUY',
                    'quantity': order_details['quantity'],
                    'price': price,
                    'timestamp': order_details['timestamp'].isoformat() if hasattr(order_details['timestamp'], 'isoformat') else order_details['timestamp'],
                    'status': 'PENDING'
                })
        
        # Sell orders
        for price, order_id in bot.sell_orders.items():
            if order_id in bot.pending_orders:
                order_details = bot.pending_orders[order_id]
                active_orders.append({
                    'id': order_id,
                    'symbol': bot.symbol,
                    'type': 'SELL',
                    'quantity': order_details['quantity'],
                    'price': price,
                    'timestamp': order_details['timestamp'].isoformat() if hasattr(order_details['timestamp'], 'isoformat') else order_details['timestamp'],
                    'status': 'PENDING'
                })
        
        return jsonify({
            'filled_orders': filled_orders,
            'active_orders': active_orders
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/grid-levels')
def get_grid_levels():
    """Get current grid levels for visualization"""
    if not bot:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    try:
        grid_levels = []
        
        # Check if grid is properly initialized
        if not bot.grid_center_price:
            return jsonify({'error': 'Grid not initialized yet'}), 200
        
        if bot.grid_center_price and bot.grid_upper_bound and bot.grid_lower_bound:
            # Calculate grid levels
            if bot.grid_type == 'arithmetic':
                spacing = (bot.grid_upper_bound - bot.grid_lower_bound) / (2 * bot.grid_levels)
                
                for i in range(-bot.grid_levels, bot.grid_levels + 1):
                    level_price = bot.grid_center_price + (i * spacing)
                    level_type = 'CENTER' if i == 0 else ('BUY' if i < 0 else 'SELL')
                    has_order = _check_order_at_level(level_price, level_type, bot)
                    grid_levels.append({
                        'price': level_price,
                        'type': level_type,
                        'has_order': has_order,
                        'level': i
                    })
            else:  # geometric
                for i in range(-bot.grid_levels, bot.grid_levels + 1):
                    multiplier = (1 + bot.grid_spacing_pct / 100) ** i
                    level_price = bot.grid_center_price * multiplier
                    level_type = 'CENTER' if i == 0 else ('BUY' if i < 0 else 'SELL')
                    has_order = _check_order_at_level(level_price, level_type, bot)
                    grid_levels.append({
                        'price': level_price,
                        'type': level_type,
                        'has_order': has_order,
                        'level': i
                    })
        else:
            return jsonify({'error': 'Grid bounds not set'}), 200
        
        # Always return a valid array, even if empty
        return jsonify(grid_levels if grid_levels else [])
        
    except Exception as e:
        print(f"Error getting grid levels: {e}")
        return jsonify({'error': str(e)}), 500

def _check_order_at_level(level_price: float, level_type: str, bot: GridTradingBot) -> bool:
    """Helper to check if an order exists at a given price level with tolerance."""
    order_book = bot.buy_orders if level_type == 'BUY' else bot.sell_orders
    for order_price_str in order_book.keys():
        try:
            order_price = float(order_price_str)
            if abs(order_price - level_price) < 0.01:
                return True
        except (ValueError, TypeError):
            continue
    return False

@app.route('/api/performance-chart')
def get_performance_chart():
    """Get performance data for chart"""
    if not bot:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    try:
        performance_data = []
        cumulative_pnl = 0.0
        
        # Calculate cumulative P&L from filled orders
        for order in bot.filled_orders:
            if order['type'] == 'SELL':
                # Find corresponding buy orders to calculate profit
                # This is a simplified calculation
                cumulative_pnl += order['fill_price'] * order['quantity'] * 0.001  # Rough estimate
            
            performance_data.append({
                'timestamp': order['timestamp'].isoformat() if hasattr(order['timestamp'], 'isoformat') else order['timestamp'],
                'cumulative_pnl': cumulative_pnl,
                'trade_pnl': order['fill_price'] * order['quantity'] * (0.001 if order['type'] == 'SELL' else -0.001)
            })
        
        return jsonify(performance_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/start-monitoring', methods=['POST'])
def start_monitoring():
    """Start real-time monitoring"""
    global monitoring_thread, monitoring_active
    
    if not bot:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    if not monitoring_active:
        monitoring_active = True
        monitoring_thread = threading.Thread(target=monitoring_loop)
        monitoring_thread.daemon = True
        monitoring_thread.start()
        return jsonify({'status': 'Monitoring started'})
    
    return jsonify({'status': 'Monitoring already active'})

@app.route('/api/stop-monitoring', methods=['POST'])
def stop_monitoring():
    """Stop real-time monitoring"""
    global monitoring_active
    monitoring_active = False
    return jsonify({'status': 'Monitoring stopped'})

@app.route('/api/start-trading', methods=['POST'])
def start_trading():
    """Start grid trading strategy"""
    global trading_thread, trading_active, bot
    
    if not bot:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    if not trading_active:
        trading_active = True
        bot.is_active = True
        trading_thread = threading.Thread(target=trading_loop)
        trading_thread.daemon = True
        trading_thread.start()
        return jsonify({'status': 'Grid trading started'})
    
    return jsonify({'status': 'Trading already active'})

@app.route('/api/stop-trading', methods=['POST'])
def stop_trading():
    """Stop grid trading strategy"""
    global trading_active, bot
    
    if bot:
        bot.is_active = False
    trading_active = False
    return jsonify({'status': 'Grid trading stopped'})

@app.route('/api/setup-grid', methods=['POST'])
def setup_grid():
    """Setup initial grid"""
    if not bot:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    try:
        current_price = bot.get_current_price()
        if current_price and bot.setup_grid(current_price):
            return jsonify({'status': 'Grid setup successful', 'center_price': current_price})
        else:
            return jsonify({'error': 'Failed to setup grid'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-trades-csv')
def export_trades_csv():
    """Export filled trades as CSV file"""
    if not bot:
        return jsonify({'error': 'Bot not initialized'}), 500

    # Get filled trades
    trades = bot.filled_orders if hasattr(bot, 'filled_orders') else []
    if not trades:
        return jsonify({'error': 'No trades found'}), 404

    # Define CSV columns
    fieldnames = ['order_id', 'timestamp', 'type', 'quantity', 'fill_price']

    # Prepare CSV data
    def generate():
        writer = csv.DictWriter(
            Response(), fieldnames=fieldnames, extrasaction='ignore')
        yield ','.join(fieldnames) + '\n'
        for trade in trades:
            row = {k: trade.get(k, '') for k in fieldnames}
            # Format timestamp if needed
            ts = row.get('timestamp')
            if hasattr(ts, 'isoformat'):
                row['timestamp'] = ts.isoformat()
            yield ','.join(str(row[k]) for k in fieldnames) + '\n'

    return Response(generate(), mimetype='text/csv', headers={
        'Content-Disposition': 'attachment; filename=trades.csv'
    })

def trading_loop():
    """Background trading loop that runs the grid strategy"""
    global trading_active, bot
    
    try:
        if bot:
            # Run the main grid strategy with the trading_active flag as control
            bot.run_grid_strategy(check_interval=30)
    except Exception as e:
        print(f"Error in trading loop: {e}")
        if bot:
            bot.logger.error(f"Trading loop error: {e}")
    finally:
        trading_active = False
        if bot:
            bot.is_active = False

def monitoring_loop():
    """Background monitoring loop for real-time updates"""
    global monitoring_active
    
    while monitoring_active:
        try:
            if bot:
                # Get current price and summary (don't interfere with trading loop)
                current_price = bot.get_current_price()
                if current_price:
                    summary = bot.get_performance_summary()
                    socketio.emit('price_update', {
                        'price': current_price,
                        'timestamp': datetime.now().isoformat()
                    })
                    socketio.emit('summary_update', summary)
                    
                    # Emit trading status
                    socketio.emit('trading_status', {
                        'trading_active': trading_active,
                        'bot_active': bot.is_active if bot else False,
                        'grid_setup': bot.grid_center_price is not None if bot else False
                    })
                
            time.sleep(10)  # Update every 10 seconds for more responsive UI
            
        except Exception as e:
            print(f"Error in monitoring loop: {e}")
            time.sleep(30)  # Wait longer if there's an error

@socketio.on('connect')
def on_connect():
    """Handle client connection"""
    print('Client connected')
    emit('status', {'msg': 'Connected to Grid Trading Dashboard'})

@socketio.on('disconnect')
def on_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

if __name__ == '__main__':
    print("🚀 Starting Grid Trading Dashboard...")
    
    # Initialize bot
    if load_bot_config():
        print("✅ Bot initialized successfully")
        print(f"📊 Trading Symbol: {bot.symbol}")
        print(f"🔧 Grid Levels: {bot.grid_levels}")
        print(f"💰 Order Amount: ₹{bot.order_amount}")
        print("\n🌐 Dashboard starting at http://localhost:5001")
        print("📈 TradingView charts and real-time monitoring enabled")
        
        socketio.run(app, debug=False, host='0.0.0.0', port=5001)
    else:
        print("❌ Failed to initialize bot. Please check your configuration.")
