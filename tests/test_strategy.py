#!/usr/bin/env python3
"""
Test script for the new initial position strategy feature
"""

import json
import sys
import os
from pathlib import Path

# Add the project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strats.grid_trading_bot import GridTradingBot

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GRID_CONFIG_PATH = PROJECT_ROOT / 'configs' / 'active' / 'grid_config.json'

def test_initial_position_strategy():
    """Test the new initial position strategy functionality"""
    print("🧪 Testing Initial Position Strategy Feature")
    print("=" * 50)
    
    # Load config
    try:
        with open(GRID_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return
    
    strategy = config['execution_settings'].get('initial_position_strategy', 'wait_for_buy')
    print(f"Testing strategy: {strategy}")
    
    # Create bot instances for both strategies
    strategies = ['wait_for_buy', 'buy_at_market']
    
    for test_strategy in strategies:
        print(f"\n🔍 Testing {test_strategy} strategy:")
        print("-" * 30)
        
        try:
            bot = GridTradingBot(
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
                state_file=f'test_state_{test_strategy}.json',
                initial_position_strategy=test_strategy
            )
            
            # Test price retrieval
            current_price = bot.get_current_price()
            if current_price:
                print(f"✅ Current price: ₹{current_price:.2f}")
                
                # Calculate what the bot would do
                buy_levels, sell_levels = bot.calculate_grid_levels(current_price)
                print(f"📈 Would create {len(buy_levels)} buy levels and {len(sell_levels)} sell levels")
                
                if test_strategy == 'wait_for_buy':
                    print("⏳ Strategy: Only buy orders would be placed initially")
                    print("   Sell orders will be placed after buy orders are filled")
                else:
                    print("🛒 Strategy: Would buy shares at market price first")
                    total_shares = sum(max(1, int(bot.order_amount / price)) for price in sell_levels)
                    print(f"   Would buy ~{total_shares} shares at market")
                    print("   Then place all sell orders immediately")
                    
            else:
                print("❌ Could not get current price")
                
        except Exception as e:
            print(f"❌ Error testing {test_strategy}: {e}")
    
    print(f"\n✅ Test completed!")
    print("\n📚 Strategy Explanation:")
    print("• wait_for_buy: Conservative approach - only sells shares you already own")
    print("• buy_at_market: Aggressive approach - buys shares immediately to enable all sell orders")

if __name__ == "__main__":
    test_initial_position_strategy()
