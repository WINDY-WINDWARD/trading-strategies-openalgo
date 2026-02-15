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

1. Implement your strategy bot in [strats](../strats).
2. Register it in [app/strategies/registry.py](../app/strategies/registry.py) using `StrategyRegistry.register(...)`.
3. If needed, add an adapter in [app/strategies](../app/strategies).
4. Ensure the strategy type is accepted by config validation in [app/models/config.py](../app/models/config.py) (`StrategyConfig.validate_strategy_type`).

## 2) Make It User-Visible (Optional)

If the strategy should appear in the web config editor dropdown, add it to [configs/active/strats.yaml](../configs/active/strats.yaml):

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

If you want it available for developers but hidden from users, do **not** add it to `strats.yaml`.

## 3) UI Form Fields per Strategy

Add/edit strategy-specific editable fields in [app/ui/templates/index.html](../app/ui/templates/index.html):
- Update `STRATEGY_FIELDS` map for your strategy key.

Without this, the strategy may be selectable but its custom fields will not be editable in the form.

## 4) API/Validation Alignment

Backend endpoints use strategy catalog validation:
- [app/api/routes/backtest.py](../app/api/routes/backtest.py)
  - `GET /api/strategies`
  - `POST /api/config` strategy allow-list check

Ensure your strategy id is:
1. registered in `StrategyRegistry`, and
2. present in `strats.yaml` if user-visible.

## 5) Documentation Updates Required

When adding a strategy, update these docs:
1. [README.md](../README.md)
   - Strategy feature summary
   - Config examples (if applicable)
   - Documentation links section
2. [docs/QUICK_START_GUIDE.md](QUICK_START_GUIDE.md)
   - New strategy registration and usage snippet
3. Strategy-specific guide (recommended)
   - Example: `docs/MY_STRATEGY_GUIDE.md`

## 6) Tests to Add/Update

1. Config catalog tests in [tests/test_strategy_catalog.py](../tests/test_strategy_catalog.py)
   - entry present
   - duplicate id validation
2. Strategy behavior tests in [tests/test_strategy.py](../tests/test_strategy.py)
3. Any adapter-specific tests if you added a custom adapter

## 7) Sanity Run

Using the repository conda environment (`trade`):
1. Run focused tests for new strategy.
2. Start web UI and verify:
   - strategy appears (if listed in `strats.yaml`)
   - dropdown switches correctly
   - strategy-specific fields render and save

---

## Common Pitfalls

- Strategy registered in code but missing in `strats.yaml` (won’t appear in UI)
- Strategy in `strats.yaml` but not registered in backend (save/run will fail)
- Strategy type not allowed by `StrategyConfig` validator
- Missing `STRATEGY_FIELDS` entry, causing incomplete config editing
