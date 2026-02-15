# scripts/launch_web.py
"""
Cross-platform script to launch the web UI using settings from configs/active/config.yaml.
"""

import os
import sys
from pathlib import Path
import uvicorn

# Add project root to the Python path to allow absolute imports
sys.path.append(str(Path(__file__).resolve().parent.parent))
from app.utils.config_loader import load_config
from app.utils.logging_config import setup_logging

if __name__ == "__main__":
    try:
        web_strategy = os.getenv("WEB_STRATEGY")

        # Load configuration to get UI host and port
        config = load_config(strategy_id=web_strategy)
        setup_logging(level=config.logging.level)

        print(f"🚀 Starting web dashboard at http://{config.ui.host}:{config.ui.port}")
        uvicorn.run(
            "app.api.main:app",
            host=config.ui.host,
            port=config.ui.port,
            reload=True,
            log_level=config.logging.level.lower()
        )
    except FileNotFoundError:
        print("❌ Error: strategy configuration file not found. Please verify configs/active/strats.yaml and strategy YAML files.")
    except Exception as e:
        print(f"❌ Failed to start web server: {e}")