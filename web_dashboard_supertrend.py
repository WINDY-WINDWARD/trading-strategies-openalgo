#!/usr/bin/env python3
"""
Supertrend Trading Bot Web Dashboard

A Flask-based web interface for monitoring and visualizing the supertrend trading bot
with Plotly charts integration and real-time updates.
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List
import os
import pandas as pd

from strats.supertrend_trading_bot import SupertrendTradingBot

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
ohlc_data = None

def load_bot_config():
    """Load configuration and initialize bot"""
    global bot
    try:
        with open('supertrend_config.json', 'r') as f:
            config = json.load(f)
        
        api_key = config['api_settings']['api_key']
        host = config['api_settings']['host']
        symbol = config['trading_settings']['symbol']
        exchange = config['trading_settings']['exchange']
        
        bot = SupertrendTradingBot(
            api_key=api_key,
            host=host,
            symbol=symbol,
            exchange=exchange,
            take_profit_pct=config['strategy_settings']['take_profit_pct'],
            stop_loss_pct=config['strategy_settings']['stop_loss_pct'],
            atr_period=config['strategy_settings']['atr_period'],
            atr_multiplier=config['strategy_settings']['atr_multiplier'],
            state_file=config['execution_settings']['state_file']
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
    return render_template('SupertrendDashboard.html')

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
        'monitoring_active': monitoring_active,
    })

@app.route('/api/ohlc-data')
def get_ohlc_data():
    """Get OHLC data for chart"""
    global ohlc_data
    print("Serving OHLC data")
    
    # If ohlc_data is not available, fetch it
    if ohlc_data is None and bot:
        print("start the trading loop to fetch data")
        return jsonify({'error': 'OHLC data not available yet'}), 404
    if ohlc_data is not None:
        try:
            # Reset index to make timestamp a column if it's not already
            df_copy = ohlc_data.copy()
            if df_copy.index.name == 'timestamp' or 'timestamp' not in df_copy.columns:
                df_copy = df_copy.reset_index()
            
            # Format data for the frontend chart
            formatted_data = {
                'timestamps': [],
                'data': []
            }
            
            for _, row in df_copy.iterrows():
                # Handle timestamp formatting - convert to string if it's a datetime
                timestamp = row.get('timestamp', row.name)
                if hasattr(timestamp, 'strftime'):
                    timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    timestamp_str = str(timestamp)
                
                formatted_data['timestamps'].append(timestamp_str)
                
                # Handle NaN values in supertrend and bands
                supertrend_val = row.get('supertrend', 0)
                if pd.isna(supertrend_val):
                    supertrend_val = 0
                
                upper_band_val = row.get('final_upper_band', 0)
                if pd.isna(upper_band_val):
                    upper_band_val = 0
                    
                lower_band_val = row.get('final_lower_band', 0)
                if pd.isna(lower_band_val):
                    lower_band_val = 0
                
                # Format: [open, high, low, close, supertrend, direction, upper_band, lower_band]
                data_point = {
                    'timestamp': timestamp_str,
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'supertrend': float(supertrend_val),
                    'direction': row.get('supertrend_direction', 'neutral'),
                    'upper_band': float(upper_band_val),
                    'lower_band': float(lower_band_val)
                }
                formatted_data['data'].append(data_point)
            
            print(f"Formatted {len(formatted_data['data'])} data points for frontend")
            return jsonify(formatted_data)
            
        except Exception as e:
            print(f"Error formatting OHLC data: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error formatting OHLC data: {str(e)}'}), 500
    else:
        return jsonify({'error': 'OHLC data not available yet'}), 404


@app.route('/api/orders')
def get_orders():
    """Get order history"""
    if not bot:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    try:
        return jsonify(bot.state['trades'])
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
    """Start supertrend trading strategy"""
    global trading_thread, trading_active, bot
    
    if not bot:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    if not trading_active:
        trading_active = True
        trading_thread = threading.Thread(target=trading_loop)
        trading_thread.daemon = True
        trading_thread.start()
        return jsonify({'status': 'Supertrend trading started'})
    
    return jsonify({'status': 'Trading already active'})

@app.route('/api/stop-trading', methods=['POST'])
def stop_trading():
    """Stop supertrend trading strategy"""
    global trading_active
    trading_active = False
    return jsonify({'status': 'Supertrend trading stopped'})

def trading_loop():
    """Background trading loop that runs the supertrend strategy"""
    global trading_active, bot, ohlc_data
    print("🚀 Supertrend trading loop started")
    while trading_active:
        try:
            # Fetch the latest historical data
            now = datetime.now()
            from_date = now - timedelta(days=90)
            data = bot.client.history(
                symbol=bot.symbol,
                exchange=bot.exchange,
                start_date=from_date.strftime('%Y-%m-%d'),
                end_date=now.strftime('%Y-%m-%d'),
                interval='5m'
            )
            print(f"Fetched {len(data)} rows of historical data")
            print("Data headings:")
            print(data.columns.tolist())
            print(data.tail())
            # Calculate the Supertrend indicator
            if isinstance(data, pd.DataFrame) and not data.empty:
                df = data
                df = bot.calculate_supertrend(df)
                ohlc_data = df
                print("head of ohlc_data with supertrend:")
                print(ohlc_data.head())
            else:
                print(f"No data received from API: {data}")
                time.sleep(60)
                continue
            
            # Get the last row of the DataFrame
            last_row = df.iloc[-1]
            current_price = bot.get_current_price()
            
            # Skip if we can't get a valid current price
            if not isinstance(current_price, (int, float)) or current_price <= 0:
                print(f"Invalid current price: {current_price}, skipping trade logic")
                time.sleep(60)
                continue

            # Check if the position is zero
            if bot.state['position'] == 0:
                # If the Supertrend direction is up, place a buy order
                if last_row['supertrend_direction'] == 'up':
                    bot.place_market_order('buy', 1)
            else:
                # If the Supertrend direction is down, place a sell order
                if last_row['supertrend_direction'] == 'down':
                    bot.place_market_order('sell', abs(bot.state['position']))
                elif len(bot.state['trades']) > 0:
                    # Check if the current price is above the entry price
                    # with take profit percentage
                    entry_price = bot.state['trades'][-1]['price']
                    if current_price >= entry_price * (1 + bot.take_profit_pct / 100):
                        bot.place_market_order('sell', abs(bot.state['position']))
                    # Check if the current price is below the entry price
                    # with stop loss percentage
                    elif current_price <= entry_price * (1 - bot.stop_loss_pct / 100):
                        bot.place_market_order('sell', abs(bot.state['position']))
            
            time.sleep(300)
        except Exception as e:
            print(f"Error in trading loop: {type(e).__name__}: {e}")
            time.sleep(60)

def monitoring_loop():
    """Background monitoring loop for real-time updates"""
    global monitoring_active
    print("🚀 Monitoring loop started")
    while monitoring_active:
        try:
            if bot:
                current_price = bot.get_current_price()
                if current_price and isinstance(current_price, (int, float)) and current_price > 0:
                    summary = bot.get_performance_summary()
                    socketio.emit('price_update', {
                        'price': current_price,
                        'timestamp': datetime.now().isoformat()
                    })
                    socketio.emit('summary_update', summary)
                    
                    socketio.emit('trading_status', {
                        'trading_active': trading_active,
                    })
                
            time.sleep(10)
            
        except Exception as e:
            print(f"Error in monitoring loop: {type(e).__name__}: {e}")
            time.sleep(30)

@socketio.on('connect')
def on_connect():
    """Handle client connection"""
    print('Client connected')
    emit('status', {'msg': 'Connected to Supertrend Trading Dashboard'})

@socketio.on('disconnect')
def on_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

if __name__ == '__main__':
    print("🚀 Starting Supertrend Trading Dashboard...")
    
    if load_bot_config():
        print("✅ Bot initialized successfully")
        print(f"📊 Trading Symbol: {bot.symbol}")
        print(f"📈 Take Profit: {bot.take_profit_pct}%")
        print(f"📉 Stop Loss: {bot.stop_loss_pct}%")
        print("\n🌐 Dashboard starting at http://localhost:5002")
        
        socketio.run(app, debug=False, host='0.0.0.0', port=5002)
    else:
        print("❌ Failed to initialize bot. Please check your configuration.")
