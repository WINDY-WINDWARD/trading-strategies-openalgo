# scripts/launch_web.py
"""
Cross-platform script to launch the web UI using settings from config.yaml.
"""

import sys
from pathlib import Path
import uvicorn

# Add project root to the Python path to allow absolute imports
sys.path.append(str(Path(__file__).resolve().parent.parent))
from app.utils.config_loader import load_config
from app.utils.logging_config import setup_logging

if __name__ == "__main__":
    try:
        # Load configuration to get UI host and port
        config = load_config()
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
        print("❌ Error: config.yaml not found. Please ensure the configuration file exists.")
    except Exception as e:
        print(f"❌ Failed to start web server: {e}")