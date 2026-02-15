# New Strategy Documentation Setup

Use this checklist whenever you add a new strategy in the future.

## Purpose

This project separates:
- **Backend availability** (strategy exists in code and can run), and
- **UI visibility** (strategy appears in the config editor dropdown).

The UI dropdown is controlled by [configs/active/strats.yaml](../configs/active/strats.yaml).

Current user-visible strategies are:
- `grid`
- `supertrend`

## 1) Add/Enable the Strategy in Code

### A. Use Universal Adapter (default path)

Use this for most strategies.

1. Implement your bot in [strats](../strats) as a `TradingBot` subclass.
2. Ensure the bot implements `run_backtest(current_price)` and all required `TradingBot` methods.
3. Ensure your bot constructor accepts `api_key` and `host` (the universal adapter injects these).
4. Register in [app/strategies/registry.py](../app/strategies/registry.py):

```python
StrategyRegistry.register('mynew', MyNewTradingBot)
```

### B. Use Custom Adapter (when required)

Create a custom adapter only if your strategy needs non-standard bar handling, heavy preprocessing, or custom lifecycle/state flow.

1. Create an adapter in [app/strategies](../app/strategies) extending `BaseStrategy`.
2. Implement the required lifecycle methods (`initialize`, `on_bar`, and adapter state handling as needed).
3. Register with adapter class in [app/strategies/registry.py](../app/strategies/registry.py):

```python
StrategyRegistry.register('mynew', MyNewTradingBot, MyNewStrategyAdapter)
```

4. Keep custom adapter constructors zero-argument (`__init__(self)`), because the registry instantiates adapters without arguments.

## 2) Update Config Validation (Required)

Registration alone is not enough. The strategy must pass `StrategyConfig` validation in [app/models/config.py](../app/models/config.py):

1. Add your strategy id to `StrategyConfig.validate_strategy_type`.
2. Add strategy-specific fields to `StrategyConfig` if they must be accepted from YAML/UI and forwarded to the adapter.
3. Keep buffer mode values aligned with code:
   - `skip_initial`
   - `fetch_additional`

## 3) Make It User-Visible (Required for UI users)

Add it to [configs/active/strats.yaml](../configs/active/strats.yaml):

```yaml
strategies:
  - id: grid
    label: Grid
    config_path: configs/active/config-grid.yaml
  - id: supertrend
    label: Supertrend
    config_path: configs/active/config-supertrend.yaml
  - id: mynew
    label: My New Strategy
    config_path: configs/active/config-mynew.yaml
```

### Field meanings
- `id`: Strategy key (must match registered strategy key)
- `label`: Display text in dropdown
- `config_path`: Strategy config path (used by backend/UI load/save/run flow)

Keep shared/base settings in [configs/active/config.yaml](../configs/active/config.yaml).
Strategy-specific files (for example `config-grid.yaml`, `config-supertrend.yaml`, `config-mynew.yaml`) are merged over the base config at load time.

## 4) UI Form Fields per Strategy

Add/edit strategy-specific editable fields in [app/ui/templates/index.html](../app/ui/templates/index.html):
- Update `STRATEGY_FIELDS` map for your strategy key.

Without this, the strategy may be selectable but its custom fields will not be editable in the form.

## 5) API/Validation Alignment

Backend endpoints use strategy catalog validation:
- [app/api/routes/backtest.py](../app/api/routes/backtest.py)
  - `GET /api/strategies`
  - `POST /api/config` strategy allow-list check

Ensure your strategy id is:
1. registered in `StrategyRegistry`, and
2. allowed by `StrategyConfig.validate_strategy_type`, and
3. present in `strats.yaml`.

## 6) Documentation Updates Required

When adding a strategy, update these docs:
1. [README.md](../README.md)
   - Strategy feature summary
   - Config examples (if applicable)
   - Documentation links section
2. [docs/QUICK_START_GUIDE.md](QUICK_START_GUIDE.md)
   - New strategy registration and usage snippet
3. Strategy-specific guide (recommended)
   - Example: `docs/MY_STRATEGY_GUIDE.md`

## 7) Tests to Add/Update

1. Config catalog tests in [tests/test_strategy_catalog.py](../tests/test_strategy_catalog.py)
   - entry present
   - duplicate id validation
2. Strategy behavior tests in [tests/test_strategy.py](../tests/test_strategy.py)
3. Any adapter-specific tests if you added a custom adapter

## 8) Sanity Run

Using the repository conda environment (`trade`):
1. Run focused tests for new strategy.
2. Start web UI and verify:
   - strategy appears (if listed in `strats.yaml`)
   - dropdown switches correctly
   - strategy-specific fields render and save

---

## Common Pitfalls

- Strategy registered in code but missing in `strats.yaml` (won’t appear in UI/API strategy list)
- Strategy in `strats.yaml` but missing in registry (run will fail)
- Strategy in registry but not allowed by `StrategyConfig` validator (config save/run fails)
- Missing `STRATEGY_FIELDS` entry, causing incomplete config editing
- Using invalid `buffer_mode` value (`use_incomplete` is not valid in current code)
