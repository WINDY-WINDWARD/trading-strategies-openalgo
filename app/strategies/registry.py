# app/strategies/registry.py
"""
Central registry for trading strategies.
Simplifies strategy loading and supports both universal and custom adapters.
"""

import logging
from typing import Dict, Type, Callable, Optional
from strats.trading_bot import TradingBot
from .base_strategy import BaseStrategy
from .universal_strategy_adapter import UniversalStrategyAdapter

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """
    Central registry for managing strategy adapters.
    
    Supports:
    - Automatic registration of simple strategies (uses UniversalStrategyAdapter)
    - Custom adapter registration for complex strategies
    - Easy strategy retrieval by name
    
    Usage:
        # Register simple strategy (auto uses Universal adapter)
        StrategyRegistry.register('grid', GridTradingBot)
        
        # Register complex strategy with custom adapter
        StrategyRegistry.register('supertrend', SupertrendTradingBot, 
                                 SupertrendStrategyAdapter)
        
        # Get strategy instance
        strategy = StrategyRegistry.get('grid')
    """
    
    _strategies: Dict[str, Callable[[], BaseStrategy]] = {}
    _bot_classes: Dict[str, Type[TradingBot]] = {}
    
    @classmethod
    def register(cls, 
                 name: str, 
                 bot_class: Type[TradingBot],
                 adapter_class: Optional[Type[BaseStrategy]] = None,
                 custom_name: Optional[str] = None) -> None:
        """
        Register a strategy in the registry.
        
        Args:
            name: Strategy identifier (e.g., 'grid', 'supertrend', 'rsi')
            bot_class: The TradingBot class to wrap
            adapter_class: Custom adapter class (optional, uses Universal if None)
            custom_name: Custom strategy name for the adapter (optional)
        
        Examples:
            # Simple strategy - uses Universal adapter
            StrategyRegistry.register('grid', GridTradingBot)
            
            # Complex strategy - uses custom adapter
            StrategyRegistry.register('supertrend', SupertrendTradingBot,
                                     SupertrendStrategyAdapter)
        """
        if name in cls._strategies:
            logger.warning(f"Strategy '{name}' already registered. Overwriting.")
        
        # Store bot class for reference
        cls._bot_classes[name] = bot_class
        
        if adapter_class is None:
            # Use universal adapter
            logger.info(f"Registering '{name}' with UniversalStrategyAdapter")
            cls._strategies[name] = lambda: UniversalStrategyAdapter(
                bot_class, 
                strategy_name=custom_name
            )
        else:
            # Use custom adapter
            logger.info(f"Registering '{name}' with custom adapter: {adapter_class.__name__}")
            cls._strategies[name] = adapter_class
        
        logger.debug(f"Strategy '{name}' registered successfully")
    
    @classmethod
    def get(cls, name: str) -> BaseStrategy:
        """
        Get a strategy adapter instance by name.
        
        Args:
            name: Strategy identifier
            
        Returns:
            Strategy adapter instance
            
        Raises:
            ValueError: If strategy not found
        """
        if name not in cls._strategies:
            available = ', '.join(cls._strategies.keys())
            raise ValueError(
                f"Unknown strategy: '{name}'. "
                f"Available strategies: {available or 'none'}"
            )
        
        # Instantiate and return strategy
        strategy_factory = cls._strategies[name]
        strategy = strategy_factory()
        
        logger.info(f"Created strategy instance: {strategy.name}")
        return strategy
    
    @classmethod
    def list_strategies(cls) -> Dict[str, str]:
        """
        List all registered strategies with their types.
        
        Returns:
            Dictionary mapping strategy name to adapter type
        """
        result = {}
        for name, factory in cls._strategies.items():
            # Determine adapter type
            temp_instance = factory()
            adapter_type = temp_instance.__class__.__name__
            result[name] = adapter_type
        return result
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        Check if a strategy is registered.
        
        Args:
            name: Strategy identifier
            
        Returns:
            True if registered, False otherwise
        """
        return name in cls._strategies
    
    @classmethod
    def get_bot_class(cls, name: str) -> Optional[Type[TradingBot]]:
        """
        Get the underlying bot class for a strategy.
        
        Args:
            name: Strategy identifier
            
        Returns:
            TradingBot class or None if not found
        """
        return cls._bot_classes.get(name)
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered strategies. Useful for testing."""
        cls._strategies.clear()
        cls._bot_classes.clear()
        logger.info("Registry cleared")


def auto_register_strategies():
    """
    Auto-register all available strategies.
    Called during module initialization.
    """
    try:
        # Import bot classes
        from strats.grid_trading_bot import GridTradingBot
        from strats.supertrend_trading_bot import SupertrendTradingBot
        
        # Import custom adapters
        from .supertrend_strategy_adapter import SupertrendStrategyAdapter
        
        # Register Grid with Universal adapter (simple strategy)
        StrategyRegistry.register('grid', GridTradingBot)
        
        # Register Supertrend with custom adapter (complex strategy)
        StrategyRegistry.register('supertrend', SupertrendTradingBot, 
                                 SupertrendStrategyAdapter)
        
        logger.info("Auto-registration complete. Registered strategies: "
                   f"{list(StrategyRegistry._strategies.keys())}")
        
    except ImportError as e:
        logger.warning(f"Could not auto-register some strategies: {e}")


# Auto-register on module import
auto_register_strategies()
