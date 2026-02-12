# app/api/routes/backtest.py
"""
API routes for running backtests and managing configuration.
"""

import asyncio
import logging
from typing import Dict, Any
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
import csv
import io

from ...utils.config_loader import (
    load_config,
    save_config,
    get_default_config,
    load_strategy_catalog,
)
from ...models.config import AppConfig
from ...core.backtest_engine import BacktestEngine
from ...strategies import StrategyRegistry
from ...data.synthetic_data import SyntheticDataProvider
from ...data.openalgo_provider import OpenAlgoDataProvider
from ..websockets import ConnectionManager

logger = logging.getLogger(__name__)
router = APIRouter()
manager = ConnectionManager()

# In-memory storage for backtest results
# In a production system, this would be a database or a persistent cache.
results_storage: Dict[str, Any] = {}

# In-memory storage for running backtest engines (for cancellation)
running_engines: Dict[str, BacktestEngine] = {}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected from WebSocket.")


@router.post("/api/backtest/run")
async def run_backtest_endpoint(background_tasks: BackgroundTasks):
    """
    Run a backtest in the background.
    """
    try:
        app_config = load_config()
        run_id = app_config.run_id
        
        # Add the backtest run to background tasks
        background_tasks.add_task(run_backtest_task, app_config)
        
        return JSONResponse(
            status_code=202,
            content={"message": "Backtest started", "run_id": run_id}
        )
    except Exception as e:
        logger.error(f"Failed to start backtest: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


async def run_backtest_task(app_config: AppConfig):
    """The actual backtest execution task."""
    run_id = app_config.run_id
    logger.info(f"Starting backtest task for run_id: {run_id}")
    await manager.broadcast({"type": "status", "message": "Fetching market data...", "run_id": run_id})

    try:
        # --- Data Fetching ---
        if app_config.data.use_synthetic or not app_config.openalgo.api_key:
            logger.info("Using synthetic data provider.")
            data_provider = SyntheticDataProvider(seed=app_config.backtest.seed)
            candles = data_provider.generate_ohlcv(
                symbol=app_config.data.symbol,
                exchange=app_config.data.exchange,
                start=datetime.fromisoformat(app_config.data.start),
                end=datetime.fromisoformat(app_config.data.end),
                timeframe=app_config.data.timeframe
            )
        else:
            logger.info("Using OpenAlgo data provider.")
            data_provider = OpenAlgoDataProvider(app_config.openalgo)
            candles = data_provider.get_historical_data(
                symbol=app_config.data.symbol, exchange=app_config.data.exchange, timeframe=app_config.data.timeframe,
                start=datetime.fromisoformat(app_config.data.start), end=datetime.fromisoformat(app_config.data.end)
            )
        if not candles:
            raise ValueError("No market data available for the given configuration.")

        await manager.broadcast({"type": "status", "message": f"Loaded {len(candles)} candles. Initializing strategy...", "run_id": run_id})

        # --- Strategy Initialization ---
        strategy_type = app_config.strategy.type
        
        # Use registry to get strategy adapter
        try:
            strategy = StrategyRegistry.get(strategy_type)
        except ValueError as e:
            raise ValueError(f"Unsupported strategy type: {strategy_type}. {e}")
        
        # Initialize strategy with config parameters
        strategy.initialize(
            **app_config.strategy.model_dump(), 
            symbol=app_config.data.symbol, 
            exchange=app_config.data.exchange,
            timeframe=app_config.data.timeframe
        )

        # --- Engine Setup ---
        engine = BacktestEngine(app_config)
        
        # Register the engine for cancellation
        running_engines[run_id] = engine
        
        # Define a progress callback for the engine
        async def progress_callback(status: Dict[str, Any]):
            await manager.broadcast({"type": "progress", "data": status, "run_id": run_id})

        engine.set_progress_callback(progress_callback)
        engine.set_strategy(strategy)

        await manager.broadcast({"type": "status", "message": "Running backtest...", "run_id": run_id})

        # --- Run Backtest ---
        # Running synchronous code in an async function
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, engine.run_backtest, candles)
        
        # Check if backtest was cancelled
        if not engine.is_running:
            logger.info(f"Backtest {run_id} was cancelled.")
            await manager.broadcast({"type": "cancelled", "message": "Backtest was cancelled by user", "run_id": run_id})
            return
        
        # Store and broadcast final result with candles data
        result_dict = result.to_dict()
        result_dict['candles'] = [candle.to_dict() for candle in candles]
        results_storage[run_id] = result_dict
        
        # Ensure data is JSON serializable before broadcasting
        import json
        try:
            json.dumps(result_dict)  # Test serialization
            await manager.broadcast({"type": "result", "data": results_storage[run_id], "run_id": run_id})
        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization failed for run_id {run_id}: {e}")
            # Try to identify problematic data
            problematic_keys = []
            for key, value in result_dict.items():
                try:
                    json.dumps(value)
                except (TypeError, ValueError):
                    problematic_keys.append(key)
            logger.error(f"Problematic keys: {problematic_keys}")
            # Send error message instead
            await manager.broadcast({"type": "error", "message": f"Results serialization failed: {str(e)}", "run_id": run_id})
        
        logger.info(f"Backtest {run_id} completed successfully.")

    except Exception as e:
        logger.error(f"Error during backtest run {run_id}: {e}", exc_info=True)
        await manager.broadcast({"type": "error", "message": str(e), "run_id": run_id})
    finally:
        # Always clean up the running engine reference
        if run_id in running_engines:
            del running_engines[run_id]


@router.post("/api/backtest/{run_id}/cancel")
async def cancel_backtest_endpoint(run_id: str):
    """
    Cancel a running backtest.
    """
    try:
        if run_id not in running_engines:
            return JSONResponse(
                status_code=404,
                content={"error": f"No running backtest found with run_id: {run_id}"}
            )
        
        engine = running_engines[run_id]
        engine.stop()
        
        logger.info(f"Backtest cancellation requested for run_id: {run_id}")
        await manager.broadcast({"type": "status", "message": "Cancelling backtest...", "run_id": run_id})
        
        return JSONResponse(
            status_code=200,
            content={"message": f"Backtest {run_id} cancellation requested"}
        )
    except Exception as e:
        logger.error(f"Failed to cancel backtest {run_id}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/backtest/running")
async def get_running_backtests():
    """
    Get list of currently running backtests.
    """
    try:
        running_list = [{"run_id": run_id, "is_running": engine.is_running} 
                       for run_id, engine in running_engines.items()]
        return JSONResponse(content={"running_backtests": running_list})
    except Exception as e:
        logger.error(f"Failed to get running backtests: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/results/{run_id}")
async def get_results(run_id: str):
    """Retrieve the results of a completed backtest."""
    result = results_storage.get(run_id)
    if result:
        # Ensure data is JSON serializable
        import json
        try:
            json.dumps(result)  # Test serialization
            return JSONResponse(content=result)
        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization failed for stored results run_id {run_id}: {e}")
            return JSONResponse(status_code=500, content={"error": f"Results data is not JSON serializable: {str(e)}"})
    return JSONResponse(status_code=404, content={"error": "Results not found"})


@router.get("/api/config")
async def get_config():
    """Get the current application configuration."""
    try:
        config = load_config()
        return JSONResponse(content=config.model_dump(mode='python'))
    except FileNotFoundError:
        # If no config exists, return a default one
        config = get_default_config()
        return JSONResponse(content=config.model_dump(mode='python'))
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/strategies")
async def get_strategies():
    """Get user-visible strategy list for UI dropdowns."""
    try:
        strategies = load_strategy_catalog()
        return JSONResponse(content={"strategies": strategies})
    except Exception as e:
        logger.error(f"Failed to load strategy catalog: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/results/{run_id}/export-csv")
async def export_trades_csv(run_id: str):
    """Export trades for a backtest run as CSV file"""
    result = results_storage.get(run_id)
    if not result or 'trades' not in result:
        return JSONResponse(status_code=404, content={"error": "No trades found for this run_id"})

    trades = result['trades']
    fieldnames = ['id', 'symbol', 'entry_time', 'exit_time', 'entry_price', 'exit_price', 'quantity', 'side', 'pnl', 'pnl_pct', 'fees', 'duration_seconds']

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for trade in trades:
        # Format timestamps if present
        trade = trade.copy()
        for k in ['entry_time', 'exit_time']:
            if k in trade and hasattr(trade[k], 'isoformat'):
                trade[k] = trade[k].isoformat()
        writer.writerow({k: trade.get(k, '') for k in fieldnames})

    output.seek(0)
    return StreamingResponse(output, media_type='text/csv', headers={
        'Content-Disposition': 'attachment; filename=trades.csv'
    })

@router.post("/api/config")
async def update_config(config_data: Dict[str, Any]):
    """Update and save the application configuration."""
    try:
        strategy_type = config_data.get("strategy", {}).get("type")
        if not strategy_type:
            return JSONResponse(status_code=400, content={"error": "strategy.type is required"})

        catalog = load_strategy_catalog()
        allowed_strategy_ids = {item["id"] for item in catalog}
        if strategy_type not in allowed_strategy_ids:
            return JSONResponse(
                status_code=400,
                content={
                    "error": (
                        f"Strategy '{strategy_type}' is not enabled for UI. "
                        f"Allowed: {sorted(allowed_strategy_ids)}"
                    )
                },
            )

        if not StrategyRegistry.is_registered(strategy_type):
            return JSONResponse(
                status_code=400,
                content={"error": f"Strategy '{strategy_type}' is not registered in backend"},
            )

        config = AppConfig(**config_data)
        save_config(config)
        return JSONResponse(content={"message": "Configuration saved successfully."})
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}", exc_info=True)
        return JSONResponse(status_code=400, content={"error": str(e)})
