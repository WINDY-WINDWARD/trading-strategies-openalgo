import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def _warehouse_test_db(tmp_path_factory: pytest.TempPathFactory) -> None:
    tmp_dir = tmp_path_factory.mktemp("warehouse_db")
    db_path = tmp_dir / "tickerData.db"
    os.environ["DW_DB_PATH"] = str(db_path)
    os.environ["DW_TESTING"] = "1"
