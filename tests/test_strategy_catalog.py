from pathlib import Path

import pytest

from app.utils.config_loader import load_strategy_catalog


def test_load_strategy_catalog_from_file(tmp_path: Path):
    catalog_path = tmp_path / "strats.yaml"
    catalog_path.write_text(
        """
strategies:
  - id: grid
    label: Grid
    config_path: configs/active/config-grid.yaml
  - id: supertrend
    label: Supertrend
    config_path: configs/active/config-supertrend.yaml
""".strip(),
        encoding="utf-8",
    )

    strategies = load_strategy_catalog(str(catalog_path))

    assert [item["id"] for item in strategies] == ["grid", "supertrend"]
    assert strategies[0]["config_path"] == "configs/active/config-grid.yaml"


def test_load_strategy_catalog_falls_back_when_missing(tmp_path: Path):
    missing_path = tmp_path / "does-not-exist.yaml"

    strategies = load_strategy_catalog(str(missing_path))

    assert [item["id"] for item in strategies] == ["grid", "supertrend"]


def test_load_strategy_catalog_rejects_duplicate_ids(tmp_path: Path):
    catalog_path = tmp_path / "strats.yaml"
    catalog_path.write_text(
        """
strategies:
  - id: grid
    label: Grid
    config_path: configs/active/config-grid.yaml
  - id: grid
    label: Grid Duplicate
    config_path: configs/active/config-supertrend.yaml
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate strategy id"):
        load_strategy_catalog(str(catalog_path))
