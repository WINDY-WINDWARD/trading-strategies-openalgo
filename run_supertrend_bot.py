#!/usr/bin/env python3
"""
Supertrend Trading Bot Launcher for OpenAlgo Platform

This script provides an easy interface to configure and run the supertrend trading bot
with safety features and monitoring capabilities.
"""

import json
import sys
import os
from datetime import datetime
from strats.supertrend_trading_bot import SupertrendTradingBot

SUPERTREND_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'configs', 'active', 'supertrend_config.json')

def load_config():
    """Load configuration from configs/active/supertrend_config.json"""
    try:
        with open(SUPERTREND_CONFIG_PATH, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"❌ Configuration file '{SUPERTREND_CONFIG_PATH}' not found.")
        print("Please create the configuration file first.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in {SUPERTREND_CONFIG_PATH}.")
        sys.exit(1)

def validate_config(config):
    """Validate configuration parameters"""
    api_key = config['api_settings']['api_key']
    if api_key == 'your-openalgo-apikey-here':
        print(f"❌ Please update your OpenAlgo API key in {SUPERTREND_CONFIG_PATH}")
        return False

    return True

def display_config_summary(config):
    """Display configuration summary"""
    print("\n📋 Supertrend Trading Configuration:")
    print("=" * 50)
    print(f"Symbol: {config['trading_settings']['symbol']}")
    print(f"Exchange: {config['trading_settings']['exchange']}")
    print(f"Take Profit: {config['strategy_settings']['take_profit_pct']}%)")
    print(f"Stop Loss: {config['strategy_settings']['stop_loss_pct']}%)")
    print(f"ATR Period: {config['strategy_settings']['atr_period']}")
    print(f"ATR Multiplier: {config['strategy_settings']['atr_multiplier']}")

def create_bot_from_config(config):
    """Create bot instance from configuration"""
    return SupertrendTradingBot(
        api_key=config['api_settings']['api_key'],
        host=config['api_settings']['host'],
        symbol=config['trading_settings']['symbol'],
        exchange=config['trading_settings']['exchange'],
        take_profit_pct=config['strategy_settings']['take_profit_pct'],
        stop_loss_pct=config['strategy_settings']['stop_loss_pct'],
        atr_period=config['strategy_settings']['atr_period'],
        atr_multiplier=config['strategy_settings']['atr_multiplier'],
        state_file=config['execution_settings']['state_file']
    )

def main():
    """Main launcher function"""
    print("🤖 Supertrend Trading Bot Launcher")
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
    print("2. Start live trading")
    print("3. View performance summary")
    print("4. Exit")

    while True:
        try:
            choice = input("\nSelect action (1-4): ").strip()

            if choice == '1':
                print("\n🔍 Testing connection...")
                current_price = bot.get_current_price()
                if current_price:
                    print(f"✅ Connection successful!")
                    print(f"Current price of {bot.symbol}: ₹{current_price:.2f}")
                else:
                    print("❌ Failed to get current price. Check your connection and API key.")

            elif choice == '2':
                print("\n⚠️  WARNING: Starting live trading mode!")
                print("This will trade with real money using the current configuration.")
                
                confirm = input("\nType 'START TRADING' to begin: ").strip()

                if confirm == 'START TRADING':
                    print("\n🚀 Starting live supertrend trading...")
                    print("Press Ctrl+C to stop the bot")

                    bot.run_strategy()
                else:
                    print("❌ Live trading cancelled.")

            elif choice == '3':
                print("\n📈 Performance Summary:")
                summary = bot.get_performance_summary()
                for key, value in summary.items():
                    print(f"   {key.replace('_', ' ').title()}: {value}")

            elif choice == '4':
                print("\n👋 Goodbye!")
                break

            else:
                print("❌ Invalid choice. Please select 1-4.")

        except KeyboardInterrupt:
            print("\n\n🛑 Bot interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
