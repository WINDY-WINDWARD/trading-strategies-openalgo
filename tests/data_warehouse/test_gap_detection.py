from datetime import datetime, timezone

from data_warehouse.core.gap_detection import detect_missing_ranges


def test_detect_missing_ranges_with_internal_gap():
    missing = detect_missing_ranges(
        start_epoch=0,
        end_epoch=300,
        existing_epochs=[0, 60, 180, 240, 300],
        interval_seconds=60,
    )

    assert missing == [(120, 120)]


def test_detect_missing_ranges_with_boundary_gaps():
    missing = detect_missing_ranges(
        start_epoch=0,
        end_epoch=300,
        existing_epochs=[120, 180],
        interval_seconds=60,
    )

    assert missing == [(0, 60), (240, 300)]


def test_detect_missing_ranges_when_complete():
    missing = detect_missing_ranges(
        start_epoch=0,
        end_epoch=180,
        existing_epochs=[0, 60, 120, 180],
        interval_seconds=60,
    )

    assert missing == []


def test_detect_missing_ranges_skips_weekend_slots() -> None:
    friday = int(datetime(2026, 2, 20, tzinfo=timezone.utc).timestamp())
    monday = int(datetime(2026, 2, 23, tzinfo=timezone.utc).timestamp())

    missing = detect_missing_ranges(
        start_epoch=friday,
        end_epoch=monday,
        existing_epochs=[friday],
        interval_seconds=24 * 60 * 60,
    )

    assert missing == [(monday, monday)]
