#!/usr/bin/env python3
"""
Grid Trading Bot Launcher for OpenAlgo Platform

This script provides an easy interface to configure and run the grid trading bot
with safety features and monitoring capabilities.
"""

import json
import sys
import os
from datetime import datetime
from strats.grid_trading_bot import GridTradingBot

def load_config():
    """Load configuration from grid_config.json"""
    try:
        with open('grid_config.json', 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print("❌ Configuration file 'grid_config.json' not found.")
        print("Please create the configuration file first.")
        sys.exit(1)
    except json.JSONDecodeError:
        print("❌ Invalid JSON in grid_config.json.")
        sys.exit(1)

def validate_config(config):
    """Validate configuration parameters"""
    api_key = config['api_settings']['api_key']
    if api_key == 'your-openalgo-apikey-here':
        print("❌ Please update your OpenAlgo API key in grid_config.json")
        return False

    if config['grid_configuration']['order_amount'] <= 0:
        print("❌ Order amount must be greater than 0")
        return False

    if config['grid_configuration']['grid_levels'] <= 0:
        print("❌ Grid levels must be greater than 0")
        return False

    return True

def display_config_summary(config):
    """Display configuration summary"""
    print("\n📋 Grid Trading Configuration:")
    print("=" * 50)
    print(f"Symbol: {config['trading_settings']['symbol']}")
    print(f"Exchange: {config['trading_settings']['exchange']}")
    print(f"Grid Levels: {config['grid_configuration']['grid_levels']} (each side)")
    print(f"Grid Spacing: {config['grid_configuration']['grid_spacing_pct']}%")
    print(f"Grid Type: {config['grid_configuration']['grid_type']}")
    print(f"Order Amount: ₹{config['grid_configuration']['order_amount']}")
    print(f"Stop Loss: {config['risk_management']['stop_loss_pct']}%")
    print(f"Take Profit: {config['risk_management']['take_profit_pct']}%")
    print(f"Auto Reset: {config['risk_management']['auto_reset']}")
    print(f"Initial Position Strategy: {config['execution_settings'].get('initial_position_strategy', 'wait_for_buy')}")

    # Calculate estimated capital requirement
    total_orders = config['grid_configuration']['grid_levels'] * 2
    estimated_capital = config['grid_configuration']['order_amount'] * total_orders
    print(f"\n💰 Estimated Capital Requirement: ₹{estimated_capital:,.2f}")
    print(f"(Based on {total_orders} total orders)")
    
    # Display strategy explanation
    strategy = config['execution_settings'].get('initial_position_strategy', 'wait_for_buy')
    if strategy == 'buy_at_market':
        print("\n📈 Strategy: Buy shares at market price to enable all sell orders immediately")
    else:
        print("\n⏳ Strategy: Wait for buy orders to fill before placing corresponding sell orders")

def create_bot_from_config(config):
    """Create bot instance from configuration"""
    return GridTradingBot(
        api_key=config['api_settings']['api_key'],
        host=config['api_settings']['host'],
        symbol=config['trading_settings']['symbol'],
        exchange=config['trading_settings']['exchange'],
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

def main():
    """Main launcher function"""
    print("🤖 Grid Trading Bot Launcher")
    print("=" * 40)

    # Load and validate configuration
    config = load_config()
    if not validate_config(config):
        sys.exit(1)

    # Display configuration
    display_config_summary(config)

    # Create bot instance
    try:
        bot = create_bot_from_config(config)
    except Exception as e:
        print(f"❌ Error creating bot: {e}")
        sys.exit(1)

    # Display current status
    print("\n📊 Current Bot Status:")
    summary = bot.get_performance_summary()
    for key, value in summary.items():
        if key not in ['symbol']:  # Skip redundant info
            print(f"   {key.replace('_', ' ').title()}: {value}")

    # Menu options
    print("\n🎮 Available Actions:")
    print("1. Test connection and get current price")
    print("2. Setup new grid (cancels existing orders)")
    print("3. Check current orders and positions")
    print("4. Start live grid trading")
    print("5. View performance summary")
    print("6. Exit")

    while True:
        try:
            choice = input("\nSelect action (1-6): ").strip()

            if choice == '1':
                print("\n🔍 Testing connection...")
                current_price = bot.get_current_price()
                if current_price:
                    print(f"✅ Connection successful!")
                    print(f"Current price of {bot.symbol}: ₹{current_price:.2f}")
                else:
                    print("❌ Failed to get current price. Check your connection and API key.")

            elif choice == '2':
                print("\n⚠️  Setting up new grid will cancel all existing orders!")
                confirm = input("Type 'CONFIRM' to proceed: ").strip()

                if confirm == 'CONFIRM':
                    print("🔧 Setting up grid...")
                    success = bot.setup_grid()
                    if success:
                        print("✅ Grid setup successful!")
                        summary = bot.get_performance_summary()
                        print(f"Active buy orders: {summary['active_buy_orders']}")
                        print(f"Active sell orders: {summary['active_sell_orders']}")
                    else:
                        print("❌ Grid setup failed!")
                else:
                    print("❌ Grid setup cancelled.")

            elif choice == '3':
                print("\n📋 Checking current status...")
                filled_orders = bot.check_filled_orders()
                if filled_orders:
                    print(f"✅ Found {len(filled_orders)} newly filled orders!")
                    for order in filled_orders:
                        print(f"   {order['type']} {order['quantity']} @ ₹{order['fill_price']:.2f}")

                summary = bot.get_performance_summary()
                print(f"\n📊 Current Status:")
                print(f"   Position: {summary['current_position']} shares")
                print(f"   Active Orders: {len(bot.pending_orders)}")
                print(f"   Realized P&L: ₹{summary.get('realized_pnl', 0):.2f}")
                print(f"   Unrealized P&L: ₹{summary['unrealized_pnl']:.2f}")

            elif choice == '4':
                print("\n⚠️  WARNING: Starting live trading mode!")
                print("This will trade with real money using the current configuration.")
                print("\nCurrent settings:")
                print(f"   Max capital exposure: ₹{config['grid_configuration']['order_amount'] * config['grid_configuration']['grid_levels'] * 2:,.2f}")
                print(f"   Stop loss: {config['risk_management']['stop_loss_pct']}%")
                print(f"   Auto reset: {config['risk_management']['auto_reset']}")

                confirm = input("\nType 'START TRADING' to begin: ").strip()

                if confirm == 'START TRADING':
                    print("\n🚀 Starting live grid trading...")
                    print("Press Ctrl+C to stop the bot")

                    check_interval = config['execution_settings']['check_interval_seconds']
                    bot.run_grid_strategy(check_interval=check_interval)
                else:
                    print("❌ Live trading cancelled.")

            elif choice == '5':
                print("\n📈 Performance Summary:")
                summary = bot.get_performance_summary()
                for key, value in summary.items():
                    print(f"   {key.replace('_', ' ').title()}: {value}")

            elif choice == '6':
                print("\n👋 Goodbye!")
                break

            else:
                print("❌ Invalid choice. Please select 1-6.")

        except KeyboardInterrupt:
            print("\n\n🛑 Bot interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
