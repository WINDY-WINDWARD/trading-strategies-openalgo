#!/usr/bin/env python3
"""
Grid Trading Backtesting System

This module provides backtesting capabilities for the grid trading strategy,
allowing users to test different configurations on historical data before
live trading.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json
import random
from typing import Dict, List, Tuple, Optional

class GridTradingBacktest:
    """
    Backtesting engine for grid trading strategies
    """

    def __init__(self,
                 initial_capital: float = 50000,
                 grid_levels: int = 5,
                 grid_spacing_pct: float = 1.5,
                 order_amount: float = 1000,
                 grid_type: str = 'arithmetic',
                 stop_loss_pct: float = 10.0,
                 take_profit_pct: float = 15.0,
                 transaction_cost_pct: float = 0.1):
        """
        Initialize backtesting parameters

        Args:
            initial_capital: Starting capital
            grid_levels: Number of grid levels each side
            grid_spacing_pct: Spacing between grid levels
            order_amount: Amount per grid order
            grid_type: 'arithmetic' or 'geometric'
            stop_loss_pct: Stop loss percentage
            take_profit_pct: Take profit percentage
            transaction_cost_pct: Transaction cost percentage
        """
        self.initial_capital = initial_capital
        self.grid_levels = grid_levels
        self.grid_spacing_pct = grid_spacing_pct
        self.order_amount = order_amount
        self.grid_type = grid_type
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.transaction_cost_pct = transaction_cost_pct / 100

        # Backtest state
        self.current_capital = initial_capital
        self.position = 0
        self.trades = []
        self.equity_curve = []
        self.grid_resets = 0
        self.grid_center = None
        self.grid_upper_bound = None
        self.grid_lower_bound = None
        self.active_orders = {'buy': {}, 'sell': {}}

    def generate_sample_data(self, 
                           days: int = 30,
                           base_price: float = 2500,
                           volatility: float = 0.02,
                           trend: float = 0.0) -> pd.DataFrame:
        """
        Generate sample price data for backtesting

        Args:
            days: Number of days
            base_price: Starting price
            volatility: Daily volatility
            trend: Daily trend (positive = upward)

        Returns:
            DataFrame with OHLCV data
        """
        np.random.seed(42)  # For reproducible results

        # Generate timestamps (every 15 minutes during market hours)
        start_date = datetime.now() - timedelta(days=days)
        timestamps = []
        current_date = start_date

        while current_date < datetime.now():
            if 9 <= current_date.hour < 16:  # Market hours
                timestamps.append(current_date)
            current_date += timedelta(minutes=15)

        # Generate price movements
        n_points = len(timestamps)

        # Random walk with trend and mean reversion
        returns = []
        price = base_price

        for i in range(n_points):
            # Add trend
            trend_component = trend / (252 * 25)  # Daily trend divided by intervals per day

            # Add volatility
            vol_component = np.random.normal(0, volatility / np.sqrt(252 * 25))

            # Add mean reversion (grid trading works well with mean-reverting assets)
            mean_reversion = -0.001 * (price - base_price) / base_price

            # Combine components
            return_val = trend_component + vol_component + mean_reversion
            returns.append(return_val)
            price *= (1 + return_val)

        # Calculate OHLCV
        closes = [base_price]
        for ret in returns:
            closes.append(closes[-1] * (1 + ret))

        closes = closes[1:]  # Remove initial value

        data = []
        for i, (ts, close) in enumerate(zip(timestamps, closes)):
            # Generate OHLC from close
            volatility_adj = volatility / np.sqrt(252 * 25)
            high = close * (1 + abs(np.random.normal(0, volatility_adj)))
            low = close * (1 - abs(np.random.normal(0, volatility_adj)))

            if i == 0:
                open_price = base_price
            else:
                open_price = closes[i-1] * (1 + np.random.normal(0, volatility_adj/2))

            volume = int(np.random.normal(100000, 20000))

            data.append({
                'timestamp': ts,
                'open': round(open_price, 2),
                'high': round(max(open_price, high, close), 2),
                'low': round(min(open_price, low, close), 2),
                'close': round(close, 2),
                'volume': max(volume, 1000)
            })

        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df

    def setup_grid(self, center_price: float) -> bool:
        """
        Setup grid around center price

        Args:
            center_price: Price to center grid around

        Returns:
            True if successful
        """
        self.grid_center = center_price
        self.grid_upper_bound = center_price * (1 + self.take_profit_pct / 100)
        self.grid_lower_bound = center_price * (1 - self.stop_loss_pct / 100)

        # Clear existing orders
        self.active_orders = {'buy': {}, 'sell': {}}

        # Calculate grid levels
        if self.grid_type == 'arithmetic':
            spacing = center_price * (self.grid_spacing_pct / 100)

            # Buy orders below center
            for i in range(1, self.grid_levels + 1):
                buy_price = center_price - (spacing * i)
                if buy_price > self.grid_lower_bound and buy_price > 0:
                    quantity = int(self.order_amount / buy_price)
                    if quantity > 0:
                        self.active_orders['buy'][buy_price] = quantity

            # Sell orders above center
            for i in range(1, self.grid_levels + 1):
                sell_price = center_price + (spacing * i)
                if sell_price < self.grid_upper_bound:
                    quantity = int(self.order_amount / sell_price)
                    if quantity > 0:
                        self.active_orders['sell'][sell_price] = quantity

        elif self.grid_type == 'geometric':
            ratio = 1 + (self.grid_spacing_pct / 100)

            # Buy orders below center
            for i in range(1, self.grid_levels + 1):
                buy_price = center_price / (ratio ** i)
                if buy_price > self.grid_lower_bound:
                    quantity = int(self.order_amount / buy_price)
                    if quantity > 0:
                        self.active_orders['buy'][buy_price] = quantity

            # Sell orders above center
            for i in range(1, self.grid_levels + 1):
                sell_price = center_price * (ratio ** i)
                if sell_price < self.grid_upper_bound:
                    quantity = int(self.order_amount / sell_price)
                    if quantity > 0:
                        self.active_orders['sell'][sell_price] = quantity

        return True

    def check_order_fills(self, current_price: float, timestamp: datetime) -> List[Dict]:
        """
        Check which orders would be filled at current price

        Args:
            current_price: Current market price
            timestamp: Current timestamp

        Returns:
            List of filled orders
        """
        filled_orders = []

        # Check buy orders (filled when price drops to or below order price)
        buy_orders_to_remove = []
        for price, quantity in self.active_orders['buy'].items():
            if current_price <= price:
                # Order filled
                cost = price * quantity * (1 + self.transaction_cost_pct)
                if self.current_capital >= cost:
                    self.current_capital -= cost
                    self.position += quantity

                    filled_orders.append({
                        'timestamp': timestamp,
                        'type': 'BUY',
                        'price': price,
                        'quantity': quantity,
                        'cost': cost
                    })

                    buy_orders_to_remove.append(price)

                    # Place corresponding sell order
                    sell_price = price * (1 + self.grid_spacing_pct / 100)
                    if sell_price < self.grid_upper_bound:
                        self.active_orders['sell'][sell_price] = quantity

        # Remove filled buy orders
        for price in buy_orders_to_remove:
            del self.active_orders['buy'][price]

        # Check sell orders (filled when price rises to or above order price)
        sell_orders_to_remove = []
        for price, quantity in self.active_orders['sell'].items():
            if current_price >= price and self.position >= quantity:
                # Order filled
                revenue = price * quantity * (1 - self.transaction_cost_pct)
                self.current_capital += revenue
                self.position -= quantity

                filled_orders.append({
                    'timestamp': timestamp,
                    'type': 'SELL',
                    'price': price,
                    'quantity': quantity,
                    'revenue': revenue
                })

                sell_orders_to_remove.append(price)

                # Place corresponding buy order
                buy_price = price * (1 - self.grid_spacing_pct / 100)
                if buy_price > self.grid_lower_bound:
                    self.active_orders['buy'][buy_price] = quantity

        # Remove filled sell orders
        for price in sell_orders_to_remove:
            del self.active_orders['sell'][price]

        return filled_orders

    def check_breakout(self, current_price: float) -> Optional[str]:
        """
        Check if price broke out of grid bounds

        Args:
            current_price: Current price

        Returns:
            'upper', 'lower', or None
        """
        if current_price > self.grid_upper_bound:
            return 'upper'
        elif current_price < self.grid_lower_bound:
            return 'lower'
        return None

    def run_backtest(self, price_data: pd.DataFrame) -> Dict:
        """
        Run complete backtest on price data

        Args:
            price_data: DataFrame with price data

        Returns:
            Dictionary with backtest results
        """
        # Initialize grid
        first_price = price_data.iloc[0]['close']
        self.setup_grid(first_price)

        # Track equity over time
        self.equity_curve = []
        self.trades = []

        for timestamp, row in price_data.iterrows():
            current_price = row['close']

            # Check for order fills
            filled_orders = self.check_order_fills(current_price, timestamp)
            self.trades.extend(filled_orders)

            # Check for breakout
            breakout = self.check_breakout(current_price)
            if breakout:
                # Reset grid
                self.grid_resets += 1
                self.setup_grid(current_price)

            # Calculate current equity
            position_value = self.position * current_price
            total_equity = self.current_capital + position_value

            self.equity_curve.append({
                'timestamp': timestamp,
                'price': current_price,
                'capital': self.current_capital,
                'position_value': position_value,
                'total_equity': total_equity,
                'position': self.position
            })

        # Calculate final results
        final_equity = self.equity_curve[-1]['total_equity'] if self.equity_curve else self.initial_capital
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100

        # Calculate trade statistics
        buy_trades = [t for t in self.trades if t['type'] == 'BUY']
        sell_trades = [t for t in self.trades if t['type'] == 'SELL']

        total_cost = sum(t.get('cost', 0) for t in buy_trades)
        total_revenue = sum(t.get('revenue', 0) for t in sell_trades)
        trading_pnl = total_revenue - total_cost

        # Calculate max drawdown
        peak_equity = self.initial_capital
        max_drawdown = 0

        for point in self.equity_curve:
            equity = point['total_equity']
            if equity > peak_equity:
                peak_equity = equity
            drawdown = (peak_equity - equity) / peak_equity * 100
            max_drawdown = max(max_drawdown, drawdown)

        return {
            'initial_capital': self.initial_capital,
            'final_equity': final_equity,
            'total_return_pct': total_return,
            'trading_pnl': trading_pnl,
            'total_trades': len(self.trades),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'grid_resets': self.grid_resets,
            'max_drawdown_pct': max_drawdown,
            'final_position': self.position,
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }

    def plot_results(self, results: Dict, price_data: pd.DataFrame):
        """Plot backtest results"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

        # 1. Price and equity curves
        equity_df = pd.DataFrame(results['equity_curve'])
        equity_df.set_index('timestamp', inplace=True)

        ax1_twin = ax1.twinx()

        # Plot price
        ax1.plot(price_data.index, price_data['close'], 'b-', alpha=0.7, label='Price')
        ax1.set_ylabel('Price (₹)', color='b')
        ax1.tick_params(axis='y', labelcolor='b')

        # Plot equity
        ax1_twin.plot(equity_df.index, equity_df['total_equity'], 'r-', linewidth=2, label='Portfolio Value')
        ax1_twin.set_ylabel('Portfolio Value (₹)', color='r')
        ax1_twin.tick_params(axis='y', labelcolor='r')

        ax1.set_title('Price vs Portfolio Value')
        ax1.grid(True, alpha=0.3)

        # 2. Returns distribution
        if len(results['trades']) > 1:
            returns = []
            for i in range(1, len(results['equity_curve'])):
                prev_equity = results['equity_curve'][i-1]['total_equity']
                curr_equity = results['equity_curve'][i]['total_equity']
                returns.append((curr_equity - prev_equity) / prev_equity * 100)

            ax2.hist(returns, bins=30, alpha=0.7, edgecolor='black')
            ax2.set_title('Returns Distribution')
            ax2.set_xlabel('Return (%)')
            ax2.set_ylabel('Frequency')
            ax2.grid(True, alpha=0.3)

        # 3. Cumulative returns
        if results['equity_curve']:
            cumulative_returns = []
            for point in results['equity_curve']:
                ret = (point['total_equity'] - self.initial_capital) / self.initial_capital * 100
                cumulative_returns.append(ret)

            ax3.plot(equity_df.index, cumulative_returns, 'g-', linewidth=2)
            ax3.axhline(y=0, color='black', linestyle='--', alpha=0.5)
            ax3.set_title('Cumulative Returns')
            ax3.set_ylabel('Return (%)')
            ax3.grid(True, alpha=0.3)

        # 4. Trade frequency
        if results['trades']:
            trade_df = pd.DataFrame(results['trades'])
            trade_df['timestamp'] = pd.to_datetime(trade_df['timestamp'])
            trade_df['hour'] = trade_df['timestamp'].dt.hour

            hourly_trades = trade_df.groupby('hour').size()
            ax4.bar(hourly_trades.index, hourly_trades.values, alpha=0.7)
            ax4.set_title('Trading Activity by Hour')
            ax4.set_xlabel('Hour of Day')
            ax4.set_ylabel('Number of Trades')
            ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('grid_backtest_results.png', dpi=300, bbox_inches='tight')
        plt.show()

        return fig


def run_backtest_example():
    """
    Run example backtest with different configurations
    """
    print("🧪 Grid Trading Strategy Backtest")
    print("=" * 40)

    # Test different configurations
    configs = [
        {
            'name': 'Conservative Grid',
            'grid_levels': 3,
            'grid_spacing_pct': 2.0,
            'order_amount': 2000,
            'stop_loss_pct': 8.0,
            'take_profit_pct': 12.0
        },
        {
            'name': 'Balanced Grid',
            'grid_levels': 5,
            'grid_spacing_pct': 1.5,
            'order_amount': 1500,
            'stop_loss_pct': 10.0,
            'take_profit_pct': 15.0
        },
        {
            'name': 'Aggressive Grid',
            'grid_levels': 8,
            'grid_spacing_pct': 1.0,
            'order_amount': 1000,
            'stop_loss_pct': 12.0,
            'take_profit_pct': 18.0
        }
    ]

    # Generate test data (ranging market)
    bt = GridTradingBacktest()
    price_data = bt.generate_sample_data(
        days=30, 
        base_price=2500, 
        volatility=0.02,  # 2% daily volatility
        trend=0.0         # No trend (ranging market)
    )

    print(f"\n📊 Generated {len(price_data)} price points for 30 days")
    print(f"Price range: ₹{price_data['close'].min():.2f} - ₹{price_data['close'].max():.2f}")

    results_summary = []

    for config in configs:
        print(f"\n🔍 Testing {config['name']}...")

        # Initialize backtester with current config
        backtester = GridTradingBacktest(
            initial_capital=50000,
            **{k: v for k, v in config.items() if k != 'name'}
        )

        # Run backtest
        results = backtester.run_backtest(price_data)

        # Store results
        results_summary.append({
            'config': config['name'],
            'total_return': results['total_return_pct'],
            'max_drawdown': results['max_drawdown_pct'],
            'total_trades': results['total_trades'],
            'grid_resets': results['grid_resets'],
            'final_equity': results['final_equity']
        })

        print(f"   Total Return: {results['total_return_pct']:.2f}%")
        print(f"   Max Drawdown: {results['max_drawdown_pct']:.2f}%")
        print(f"   Total Trades: {results['total_trades']}")
        print(f"   Grid Resets: {results['grid_resets']}")

        # Plot results for the balanced configuration
        if config['name'] == 'Balanced Grid':
            print("   Creating detailed analysis charts...")
            backtester.plot_results(results, price_data)

    # Summary comparison
    print("\n" + "="*60)
    print("📈 BACKTEST RESULTS SUMMARY")
    print("="*60)

    print(f"{'Configuration':<20} {'Return %':<10} {'Drawdown %':<12} {'Trades':<8} {'Resets':<8}")
    print("-" * 60)

    for result in results_summary:
        print(f"{result['config']:<20} {result['total_return']:<10.2f} "
              f"{result['max_drawdown']:<12.2f} {result['total_trades']:<8} {result['grid_resets']:<8}")

    # Find best performing configuration
    best_config = max(results_summary, key=lambda x: x['total_return'])
    print(f"\n🏆 Best Performing: {best_config['config']}")
    print(f"   Return: {best_config['total_return']:.2f}%")

    print("\n💡 Key Insights:")
    print("• Grid trading works best in ranging/sideways markets")
    print("• Tighter grids capture more small movements but increase costs")
    print("• Wider grids are more stable but may miss opportunities")
    print("• Proper risk management (stop-loss) is crucial")
    print("• Consider transaction costs in real trading")

    print("\n✅ Backtest completed! Check 'grid_backtest_results.png' for detailed charts.")


if __name__ == "__main__":
    run_backtest_example()
