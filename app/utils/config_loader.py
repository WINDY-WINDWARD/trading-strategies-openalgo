# app/utils/config_loader.py
"""
Configuration loading utilities with environment variable support.
"""

import os
import yaml
from typing import Dict, Any
from pathlib import Path
import re
from ..models.config import AppConfig


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


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """
    Load configuration from YAML file with environment variable substitution.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Parsed configuration object
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
        ValueError: If configuration is invalid
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        # Read and substitute environment variables
        with open(config_file, 'r', encoding='utf-8') as f:
            config_content = f.read()
        
        substituted_content = substitute_env_vars(config_content)
        
        # Parse YAML
        config_data = yaml.safe_load(substituted_content)
        
        if not isinstance(config_data, dict):
            raise ValueError("Configuration file must contain a YAML mapping")
        
        # Create and validate configuration
        return AppConfig(**config_data)
        
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML in configuration file: {e}")
    except Exception as e:
        raise ValueError(f"Error loading configuration: {e}")


def save_config(config: AppConfig, config_path: str = "config.yaml") -> None:
    """
    Save configuration to YAML file.
    
    Args:
        config: Configuration object to save
        config_path: Path to save configuration file
    """
    config_data = config.to_dict()
    
    with open(config_path, 'w', encoding='utf-8') as f:
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
