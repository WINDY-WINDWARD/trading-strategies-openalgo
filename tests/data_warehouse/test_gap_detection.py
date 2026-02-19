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
