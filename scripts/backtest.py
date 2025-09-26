# scripts/backtest.py
"""
CLI script for running backtests.
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

import click
from datetime import datetime
from app.utils.config_loader import load_config, save_config, get_default_config
from app.utils.logging_config import setup_logging
from app.data.synthetic_data import SyntheticDataProvider
from app.data.openalgo_provider import SyncOpenAlgoDataProvider
from app.core.backtest_engine import BacktestEngine
from app.strategies.grid_strategy_adapter import GridStrategyAdapter


@click.command()
@click.option('--config', '-c', default='config.yaml', help='Configuration file path')
@click.option('--output', '-o', default=None, help='Output directory for results')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging')
def main(config, output, verbose):
    """Run backtest from command line."""
    
    try:
        # Load configuration
        click.echo(f"Loading configuration from {config}")
        app_config = load_config(config)
        
        # Setup logging
        log_level = "DEBUG" if verbose else app_config.logging.level
        setup_logging(
            level=log_level,
            format_str=app_config.logging.format,
            log_file=app_config.logging.file
        )
        
        click.echo(f"Starting backtest: {app_config.data.symbol} on {app_config.data.exchange}")
        
        # Get market data
        click.echo("Fetching market data...")
        
        if app_config.data.use_synthetic or not app_config.openalgo.api_key:
            # Use synthetic data
            click.echo("Using synthetic data")
            data_provider = SyntheticDataProvider(seed=app_config.backtest.seed)
            
            start_date = datetime.fromisoformat(app_config.data.start)
            end_date = datetime.fromisoformat(app_config.data.end)
            
            candles = data_provider.generate_ohlcv(
                symbol=app_config.data.symbol,
                exchange=app_config.data.exchange,
                start=start_date,
                end=end_date,
                timeframe=app_config.data.timeframe
            )
        else:
            # Use OpenAlgo data
            click.echo("Using OpenAlgo data")
            data_provider = SyncOpenAlgoDataProvider(app_config.openalgo)
            
            start_date = datetime.fromisoformat(app_config.data.start)
            end_date = datetime.fromisoformat(app_config.data.end)
            
            candles = data_provider.get_historical_data(
                symbol=app_config.data.symbol,
                exchange=app_config.data.exchange,
                timeframe=app_config.data.timeframe,
                start=start_date,
                end=end_date
            )
        
        if not candles:
            click.echo("ERROR: No market data available", err=True)
            sys.exit(1)
        
        click.echo(f"Loaded {len(candles)} candles")
        
        # Initialize strategy
        click.echo("Initializing grid trading strategy...")
        strategy = GridStrategyAdapter()
        strategy.initialize(
            # Pass all strategy parameters from config
            symbol=app_config.data.symbol,
            exchange=app_config.data.exchange,
            grid_levels=app_config.strategy.grid_levels,
            grid_spacing_pct=app_config.strategy.grid_spacing_pct,
            order_amount=app_config.strategy.order_amount,
            grid_type=app_config.strategy.grid_type,
            stop_loss_pct=app_config.strategy.stop_loss_pct,
            take_profit_pct=app_config.strategy.take_profit_pct,
            auto_reset=app_config.strategy.auto_reset,
            initial_position_strategy=app_config.strategy.initial_position_strategy
        )
        
        # Initialize backtest engine
        engine = BacktestEngine(app_config)
        engine.set_strategy(strategy)
        
        # Run backtest
        click.echo("Running backtest...")
        result = engine.run_backtest(candles)
        
        # Display results
        click.echo("\n" + "="*50)
        click.echo("BACKTEST RESULTS")
        click.echo("="*50)
        
        metrics = result.metrics
        click.echo(f"Total Return: {metrics.total_return:.2f} ({metrics.total_return_pct:.2f}%)")
        click.echo(f"Annualized Return: {metrics.annualized_return:.2f}%")
        click.echo(f"Max Drawdown: {metrics.max_drawdown:.2f} ({metrics.max_drawdown_pct:.2f}%)")
        click.echo(f"Sharpe Ratio: {metrics.sharpe_ratio:.3f}" if metrics.sharpe_ratio else "Sharpe Ratio: N/A")
        click.echo(f"Total Trades: {metrics.total_trades}")
        click.echo(f"Win Rate: {metrics.win_rate:.1f}%")
        click.echo(f"Profit Factor: {metrics.profit_factor:.2f}" if metrics.profit_factor else "Profit Factor: N/A")
        
        # Save results
        if output:
            output_dir = Path(output)
            output_dir.mkdir(exist_ok=True)
            
            # Save JSON
            json_path = output_dir / f"{result.run_id}_results.json"
            result.save_to_json(str(json_path))
            
            # Save trades CSV
            csv_path = output_dir / f"{result.run_id}_trades.csv"
            result.save_to_csv(str(csv_path))
            
            click.echo(f"\nResults saved to:")
            click.echo(f"  JSON: {json_path}")
            click.echo(f"  CSV:  {csv_path}")
        
        click.echo(f"\nRun ID: {result.run_id}")
        click.echo("Backtest completed successfully!")
        
    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
