# app/utils/config_loader.py
"""
Configuration loading utilities with environment variable support.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

from ..models.config import AppConfig


DEFAULT_CONFIG_PATH = "configs/active/config.yaml"
DEFAULT_STRATEGIES_PATH = "configs/active/strats.yaml"

DEFAULT_STRATEGY_CATALOG: List[Dict[str, str]] = [
    {
        "id": "grid",
        "label": "Grid",
        "config_path": "configs/active/config-grid.yaml",
    },
    {
        "id": "supertrend",
        "label": "Supertrend",
        "config_path": "configs/active/config-supertrend.yaml",
    },
]


def substitute_env_vars(config_str: str) -> str:
    """
    Substitute environment variables in config string.
    
    Args:
        config_str: Configuration string with ${VAR_NAME} placeholders
        
    Returns:
        Configuration string with environment variables substituted
    """
    pattern = r'\$\{([^}]+)\}'
    
    def replacer(match):
        var_name = match.group(1)
        # Get default value if specified (VAR_NAME:default_value)
        if ':' in var_name:
            var_name, default_value = var_name.split(':', 1)
            return os.getenv(var_name, default_value)
        else:
            return os.getenv(var_name, match.group(0))  # Keep original if not found
    
    return re.sub(pattern, replacer, config_str)


def _read_yaml_mapping(config_path: str) -> Dict[str, Any]:
    """Read YAML file into a mapping with environment substitution."""
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file, 'r', encoding='utf-8') as f:
        config_content = f.read()

    substituted_content = substitute_env_vars(config_content)
    config_data = yaml.safe_load(substituted_content)

    if not isinstance(config_data, dict):
        raise ValueError("Configuration file must contain a YAML mapping")

    return config_data


def _merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries where override wins."""
    merged = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_config_from_path(
    config_path: str,
    base_config_path: str | None = None,
) -> AppConfig:
    """
    Load configuration from YAML file with environment variable substitution.
    
    Args:
        config_path: Concrete path to configuration file
        
    Returns:
        Parsed configuration object
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
        ValueError: If configuration is invalid
    """
    try:
        config_data = _read_yaml_mapping(config_path)

        if base_config_path and Path(base_config_path).exists():
            base_data = _read_yaml_mapping(base_config_path)
            config_data = _merge_dicts(base_data, config_data)

        # Create and validate configuration
        return AppConfig(**config_data)

    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML in configuration file: {e}")
    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValueError(f"Error loading configuration: {e}")


def get_strategy_config_path(
    strategy_id: str,
    strategies_path: str = DEFAULT_STRATEGIES_PATH,
) -> str:
    """Resolve config path for a strategy id from strategy catalog."""
    normalized_id = strategy_id.strip().lower()
    catalog = load_strategy_catalog(strategies_path)

    for item in catalog:
        if item["id"] == normalized_id:
            return item["config_path"]

    allowed = ", ".join(sorted(item["id"] for item in catalog))
    raise ValueError(f"Unknown strategy id '{strategy_id}'. Allowed: {allowed}")


def get_default_strategy_id(strategies_path: str = DEFAULT_STRATEGIES_PATH) -> str:
    """Get default strategy id from catalog, falling back to built-in defaults."""
    try:
        catalog = load_strategy_catalog(strategies_path)
        if catalog:
            return catalog[0]["id"]
    except Exception:
        pass
    return DEFAULT_STRATEGY_CATALOG[0]["id"]


def load_config(
    config_path: str | None = None,
    strategy_id: str | None = None,
) -> AppConfig:
    """
    Load configuration with strategy-aware resolution.

    Resolution order:
    1) explicit config_path
    2) explicit strategy_id mapped via strategy catalog
    3) default strategy from strategy catalog
    4) legacy fallback to DEFAULT_CONFIG_PATH
    """
    if config_path:
        base_path = DEFAULT_CONFIG_PATH if config_path != DEFAULT_CONFIG_PATH else None
        return _load_config_from_path(config_path, base_config_path=base_path)

    if strategy_id:
        strategy_path = get_strategy_config_path(strategy_id)
        return _load_config_from_path(strategy_path, base_config_path=DEFAULT_CONFIG_PATH)

    try:
        default_strategy = get_default_strategy_id()
        strategy_path = get_strategy_config_path(default_strategy)
        return _load_config_from_path(strategy_path, base_config_path=DEFAULT_CONFIG_PATH)
    except Exception:
        return _load_config_from_path(DEFAULT_CONFIG_PATH)


def save_config(
    config: AppConfig,
    config_path: str | None = None,
    strategy_id: str | None = None,
) -> None:
    """
    Save configuration to YAML file.
    
    Args:
        config: Configuration object to save
        config_path: Optional explicit path to save configuration file
        strategy_id: Optional strategy id to resolve strategy-specific config path
    """
    target_path = config_path

    if not target_path:
        try:
            strategy_key = strategy_id or config.strategy.type
            target_path = get_strategy_config_path(strategy_key)
        except Exception:
            target_path = DEFAULT_CONFIG_PATH

    path_obj = Path(target_path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    config_data = config.to_dict()

    with open(path_obj, 'w', encoding='utf-8') as f:
        yaml.dump(config_data, f, default_flow_style=False, indent=2)


def get_default_config() -> AppConfig:
    """
    Get default configuration for development/testing.
    
    Returns:
        Default configuration object
    """
    default_config = {
        "openalgo": {
            "api_key": "",
            "base_url": "http://127.0.0.1:8800",
            "timeout": 30,
            "retry_attempts": 3
        },
        "data": {
            "exchange": "NSE",
            "symbol": "RELIANCE",
            "timeframe": "1h",
            "start": "2023-01-01",
            "end": "2023-12-31",
            "cache_dir": ".cache/data",
            "use_synthetic": True
        },
        "backtest": {
            "initial_cash": 100000.0,
            "fee_bps": 5.0,
            "slippage_bps": 2.0,
            "seed": 42,
            "candle_execution": True,
            "commission_per_trade": 0.0
        },
        "strategy": {
            "type": "grid",
            "grid_levels": 10,
            "grid_spacing_pct": 1.0,
            "order_amount": 1000.0,
            "grid_type": "arithmetic",
            "stop_loss_pct": 5.0,
            "take_profit_pct": 10.0,
            "auto_reset": True,
            "initial_position_strategy": "wait_for_buy"
        },
        "ui": {
            "host": "0.0.0.0",
            "port": 8000,
            "debug": False,
            "title": "Grid Trading Backtester"
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": "backtest.log"
        }
    }
    
    return AppConfig(**default_config)


def load_strategy_catalog(strategies_path: str = DEFAULT_STRATEGIES_PATH) -> List[Dict[str, str]]:
    """
    Load strategy catalog from YAML.

    Expected format:
      strategies:
        - id: grid
          label: Grid
          config_path: configs/active/config.yaml

    Falls back to DEFAULT_STRATEGY_CATALOG if file is missing.
    """
    path = Path(strategies_path)
    if not path.exists():
        return [item.copy() for item in DEFAULT_STRATEGY_CATALOG]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in strategy catalog: {e}")

    if not isinstance(data, dict):
        raise ValueError("Strategy catalog must be a YAML mapping")

    strategies = data.get("strategies")
    if not isinstance(strategies, list):
        raise ValueError("'strategies' must be a list")

    normalized: List[Dict[str, str]] = []
    seen_ids = set()
    for index, item in enumerate(strategies):
        if not isinstance(item, dict):
            raise ValueError(f"Strategy entry at index {index} must be a mapping")

        strategy_id = str(item.get("id", "")).strip().lower()
        label = str(item.get("label", "")).strip()
        config_path = str(item.get("config_path", "")).strip()

        if not strategy_id:
            raise ValueError(f"Strategy entry at index {index} is missing 'id'")
        if not label:
            raise ValueError(f"Strategy '{strategy_id}' is missing 'label'")
        if not config_path:
            raise ValueError(f"Strategy '{strategy_id}' is missing 'config_path'")
        if strategy_id in seen_ids:
            raise ValueError(f"Duplicate strategy id in catalog: '{strategy_id}'")

        seen_ids.add(strategy_id)
        normalized.append(
            {
                "id": strategy_id,
                "label": label,
                "config_path": config_path,
            }
        )

    if not normalized:
        raise ValueError("Strategy catalog is empty")

    return normalized
