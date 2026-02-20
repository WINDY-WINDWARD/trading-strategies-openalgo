from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

try:
    from .api.api import create_app
    from .logging_config import configure_from_environment
except ImportError:  # pragma: no cover - supports direct execution
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from data_warehouse.api.api import create_app
    from data_warehouse.logging_config import configure_from_environment


env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

configure_from_environment()
app = create_app()
