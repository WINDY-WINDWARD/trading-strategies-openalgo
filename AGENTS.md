AGENTS.md

Purpose
- This file contains build, lint and test commands and a concise style guide
  for automated agents working on this repository. Use it as the canonical
  source for how to run, test, and change code safely.

Repository setup
- Python 3.10+ is recommended; project was developed with CPython 3.11/3.12
- activate conda env:
  - conda activate trade
- Install dependencies:
  - make dev
  - OR: pip install -r requirements.txt

Common commands
- Run the web dashboard: `make web` (launches `scripts/launch_web.py`)
- Run a backtest (CLI): `python -m scripts.backtest --config configs/active/config.yaml`
- Start the grid bot (example): `python run_grid_bot.py`
- Start live trading: `make live` (launches `launch_trading_bot.py`)
- Clean cache files: `make clean` (removes __pycache__, .pyc, etc.)

Test commands
- Run all tests: `python run_tests.py` or `pytest -q`
- Run a single test file: `pytest tests/test_strategy.py -q`
- Run a single test case by nodeid:
  - `pytest tests/test_strategy.py::test_some_behavior -q`
  - Use `-k <expr>` to filter by name: `pytest -k "openalgo and provider" -q`
- Run tests with coverage (if coverage is installed):
  - `pytest --cov=app --cov-report=term-missing`
- Windows helper: `run_tests.bat` is provided for convenience.

Linting and formatting
- Formatting (auto): `black .` (project follows Black defaults)
- Import sorting: `isort .` before committing
- Linting: `ruff check .` or `flake8 .` — address style issues
- Optional static types: `mypy app` (if mypy added to dev deps)
- Recommended pre-commit hooks (suggested): black, isort, ruff/flake8

Running commands as an agent
- Always run tests after changing behavior (unit tests + relevant integration
  tests). For a focused change, run the single test(s) touching the modified
  modules first using the nodeid or `-k` expression.
- Keep `conda run -n trade` when spawning subprocesses so tests import from local code.
  Example: `conda run -n trade pytest tests/test_openalgo.py`
- ALWAYS use the CONDA environment so dependencies are available when running scripts.

Code style guidelines (for automated agents)

1) General philosophy
- Keep code small, explicit, and well-typed. Prefer readability over cleverness.
- Write code assuming a human will read the next change; add short, clarifying
  comments only where intent is non-obvious.

2) Formatting and imports
- Use Black for formatting; run `black .` before committing.
- Use isort to group imports in the order: stdlib, third-party, local packages.
  Example grouping:
  - import os
  - import logging
  - import numpy as np
  - from app.utils import config_loader
- Avoid wildcard imports (`from module import *`). Prefer explicit imports.

3) Typing
- Add type hints on public functions/methods and on return types for clarity.
- Use typing.Optional[T] for values that may be None, and avoid `Any` unless
  absolutely necessary. When `Any` is required, add a short comment why.
- Keep runtime and type-checker behavior consistent — don't rely on type-only
  constructs to change runtime control flow.

4) Naming
- Modules and functions: snake_case (e.g., `calculate_pnl`, `backtest_engine`).
- Classes: PascalCase (e.g., `GridTradingBot`).
- Constants: UPPER_SNAKE (e.g., `DEFAULT_SPREAD_PCT`).
- Tests: test_ prefix on files and functions (`tests/test_order_execution.py`,
  `def test_partial_fill_behavior():`). Use descriptive names for assertions.

5) Files and project layout
- Keep related classes and small helpers in the same module; if a file gets
  larger than ~400 lines consider extracting helpers into another module.

6) Error handling
- Don't use bare `except:`. Catch specific exceptions (e.g., `except ValueError:`)
  or `except (ValueError, KeyError):` when appropriate.
- Use `raise` without arguments inside an `except` block to re-raise the same
  exception after additional logging/cleanup.
- Use custom exception classes for domain-level errors (e.g., `class
  DataFetchError(Exception): ...`). Keep exceptions small and descriptive.

7) Logging
- Use the module-level logger: `logger = logging.getLogger(__name__)`.
- Avoid print() for runtime diagnostics; use `logger.debug/info/warning/error`.
- Log exceptions with `logger.exception()` when catching and not re-raising.

8) Tests
- Tests live in `tests/` and use pytest. Keep tests small and deterministic.
- Use fixtures for shared setup and `tmp_path` for filesystem side effects.
- Test names should describe the behaviour under test. Use parametrization to
  reduce duplication when testing the same behavior with multiple inputs.
- When changing core behavior, run the full test suite locally before pushing.

9) Design and architecture notes
- Favor dependency injection for external systems (e.g., OpenAlgo client) so
  tests can pass a mock client easily.
- Avoid global mutable state. If state is required, make it explicit through
  class instances or context managers.
- Prefer pure functions for computations (deterministic, side-effect-free).

10) Commits and PRs
- Keep commits focused and small. One logical change per commit.
- Commit message style: short title (<=72 chars), blank line, one-paragraph
  description of why the change was made.
- When adding new behavior, include or update tests that cover it.

11) CI / Automation guidance
- CI should run: formatting (black --check), isort --check-only, ruff/flake8,
  pytest (with coverage), and (optionally) mypy. Failing checks should block merge.

12) Security and secrets
- Never commit secrets or API keys. Use environment variables (e.g., `OPENALGO_API_KEY`)
  and document required env vars in `README.md` or `configs/active/config.yaml`.

13) When in doubt
- Write a failing test that demonstrates the bug or desired behavior, then
  implement the fix (TDD-first when practical).

Next steps for agents
- After adding/patching code run the single test(s) that touch the area:
  - `pytest path/to/test.py::test_name -q`
- Run `black . && isort . && ruff check .` locally before creating a PR.

Contact / docs
- For high-level project documentation see `README.md` and `docs/`.
