# app/strategies/__init__.py
"""
Trading strategies and adapters.
"""

from .base_strategy import BaseStrategy
from .grid_strategy_adapter import GridStrategyAdapter
from .supertrend_strategy_adapter import SupertrendStrategyAdapter
from .universal_strategy_adapter import UniversalStrategyAdapter
from .registry import StrategyRegistry
from . import hooks

__all__ = [
    "BaseStrategy",
    "GridStrategyAdapter",
    "SupertrendStrategyAdapter",
    "UniversalStrategyAdapter",
    "StrategyRegistry",
    "hooks",
]
