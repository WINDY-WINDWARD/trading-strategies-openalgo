# New Strategy Documentation Setup for LIVE Trading

Use this checklist when adding a new strategy that must run in live mode (CLI launcher + optional web dashboard), not just backtesting.

## Purpose

This project has separate integration paths:
- **Backtesting path**: strategy registry + adapters + backtest API/UI.
- **Live trading path**: strategy bot + live launcher + live dashboard backend/frontend.

This guide covers the **live trading path**.

## Reference Implementations

Use these as templates:
- [run_grid_bot.py](../run_grid_bot.py)
- [run_supertrend_bot.py](../run_supertrend_bot.py)
- [strats/grid_trading_bot.py](../strats/grid_trading_bot.py)
- [strats/supertrend_trading_bot.py](../strats/supertrend_trading_bot.py)
- [web_dashboard_grid_trading.py](../web_dashboard_grid_trading.py)
- [web_dashboard_supertrend.py](../web_dashboard_supertrend.py)
- [templates/Griddashboard.html](../templates/Griddashboard.html)
- [templates/SupertrendDashboard.html](../templates/SupertrendDashboard.html)

---

## 1) Implement Live-Capable Strategy Bot

Create your bot under [strats](../strats) and inherit from `TradingBot`.

Minimum live requirements (mirroring current bots):
1. Constructor accepts at least `api_key`, `host`, `symbol`, `exchange`, and strategy params.
2. Persistent state handling:
   - `save_state()`
   - `load_state()`
3. Order lifecycle methods:
   - `place_market_order()`
   - `place_limit_order()`
   - `cancel_all_orders()`
   - `check_filled_orders()`
4. Market/query methods:
   - `get_current_price()`
   - `get_performance_summary()`
   - `calculate_unrealized_pnl()`
5. Live loop method:
   - `run_strategy(...)` with a stop flag (`self.is_running` or `self.is_active`).
6. Backtest compatibility method:
   - `run_backtest(current_price)` (required by `TradingBot` interface).

### Live loop pattern
- Poll latest price/data.
- Update fills and positions.
- Apply entry/exit logic.
- Persist state periodically.
- Sleep with safe retry/backoff on exceptions.

---

## 2) Create CLI Launcher Script

Create `run_<strategy>_bot.py` at repo root, following [run_grid_bot.py](../run_grid_bot.py) and [run_supertrend_bot.py](../run_supertrend_bot.py).

Required launcher parts:
1. `load_config()` from a strategy config file.
2. `validate_config()` with API key and strategy-specific numeric checks.
3. `display_config_summary()` for operator visibility.
4. `create_bot_from_config()` mapping config fields to bot constructor.
5. Interactive menu with at least:
   - test connection/price
   - start live trading
   - view summary
   - exit

### Critical method alignment
Launcher must call the live method that actually exists on your bot (normally `run_strategy`).

---

## 3) Add Live Config File and Schema

Current live launchers/dashboards expect JSON files:
- `configs/active/grid_config.json`
- `configs/active/supertrend_config.json`

Create a similar file for your strategy (example: `configs/active/mystrategy_config.json`).

Suggested schema (based on existing launchers):

```json
{
  "api_settings": {
    "api_key": "your-openalgo-apikey-here",
    "host": "http://127.0.0.1:8800"
  },
  "trading_settings": {
    "symbol": "RELIANCE",
    "exchange": "NSE"
  },
  "strategy_settings": {
    "my_param": 10
  },
  "risk_management": {
    "stop_loss_pct": 5.0,
    "take_profit_pct": 10.0,
    "auto_reset": true
  },
  "execution_settings": {
    "state_file": "mystrategy_state.json",
    "check_interval_seconds": 30,
    "initial_position_strategy": "wait_for_buy"
  }
}
```

Use only the sections your strategy needs; keep naming consistent with launcher parsing.

---

## 4) Add Live Web Dashboard Backend (Optional but Recommended)

Create `web_dashboard_<strategy>.py` using [web_dashboard_grid_trading.py](../web_dashboard_grid_trading.py) or [web_dashboard_supertrend.py](../web_dashboard_supertrend.py).

### Required backend pieces
1. Flask app + SocketIO setup.
2. Global bot instance and live flags (`monitoring_active`, `trading_active`).
3. `load_bot_config()` that builds your bot from JSON config.
4. Core routes:
   - `GET /` (template)
   - `GET /api/summary`
   - `GET /api/orders`
   - `POST /api/start-monitoring`
   - `POST /api/stop-monitoring`
   - `POST /api/start-trading`
   - `POST /api/stop-trading`
5. Strategy-specific routes as needed:
   - Grid style: `/api/grid-levels`, `/api/setup-grid`, `/api/trading-status`
   - Supertrend style: `/api/ohlc-data`, `/api/trading-status`
6. Background loops:
   - `trading_loop()` to run strategy logic.
   - `monitoring_loop()` to emit updates every N seconds.
7. Socket events emitted to UI:
   - `price_update`
   - `summary_update`
   - `trading_status`

---

## 5) Add Live Dashboard Frontend Template (Optional)

Create `templates/<YourStrategy>Dashboard.html` based on:
- [templates/Griddashboard.html](../templates/Griddashboard.html)
- [templates/SupertrendDashboard.html](../templates/SupertrendDashboard.html)

Frontend should:
1. Render summary metrics.
2. Fetch initial data from backend API endpoints.
3. Subscribe to Socket.IO updates (`price_update`, `summary_update`, `trading_status`).
4. Wire control buttons for start/stop monitoring and start/stop trading.
5. Show safe confirmation prompts before live trading actions.

---

## 6) Safety and Operations Checklist

Before enabling live mode:
- API key is real (not placeholder).
- Symbol/exchange validated against broker/exchange.
- Position sizing and max exposure constraints are enforced.
- Stop-loss/take-profit logic is tested.
- State file path is writable and recoverable.
- Manual stop path works (menu exit, stop API, Ctrl+C).

---

## 7) Sanity Run (Live Path)

Using the `trade` conda environment:
1. Run launcher and test connection/price.
2. Run dashboard backend and open UI.
3. Start monitoring, verify summary/price updates.
4. Start trading, verify status transitions and order updates.
5. Stop trading, verify graceful shutdown and persisted state.

---

## Common Pitfalls (Observed in Current Live Files)

- **Config file mismatch**: launchers/dashboards currently look for JSON under `configs/active/*_config.json`, while backtesting docs mainly discuss YAML.
- **Method name mismatch**: some live flows call `run_grid_strategy(...)` while the grid bot defines `run_strategy(...)`.
- **Dashboard/API drift**: template expects endpoints/events that backend does not expose (or names differ).
- **No stop flag wiring**: live loop cannot stop cleanly when trading is disabled.
- **State not persisted**: bot restarts with inconsistent position/orders.

---

## Documentation Updates Required

When adding a live strategy, also update:
1. [README.md](../README.md)
   - launcher command
   - live config file location
   - dashboard entrypoint (if any)
2. [docs/QUICK_START_GUIDE.md](QUICK_START_GUIDE.md)
   - mention live path for your strategy
3. [docs/NEW_STRATEGY_DOCUMENTATION_SETUP.md](NEW_STRATEGY_DOCUMENTATION_SETUP.md)
   - add cross-link to this live setup guide
