from __future__ import annotations


TIMEFRAME_TO_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
    "1M": 2592000,
}


def detect_missing_ranges(
    start_epoch: int,
    end_epoch: int,
    existing_epochs: list[int],
    interval_seconds: int,
) -> list[tuple[int, int]]:
    """
    Detect contiguous gaps in a time series between two epochs.

    The function assumes that data points in `existing_epochs` should occur at
    a fixed cadence of `interval_seconds` seconds. It scans the timeline from
    `start_epoch` to `end_epoch`, compares the expected positions of data
    points against the provided `existing_epochs`, and returns ranges where
    one or more consecutive data points are missing.

    Parameters
    ----------
    start_epoch:
        Inclusive start of the time range (Unix timestamp in seconds) to
        inspect for missing data.
    end_epoch:
        Inclusive end of the time range (Unix timestamp in seconds) to inspect
        for missing data. If `end_epoch` is earlier than `start_epoch`, no
        ranges are returned.
    existing_epochs:
        List of Unix timestamps (in seconds) where data points already exist.
        Timestamps outside the [`start_epoch`, `end_epoch`] window are ignored.
    interval_seconds:
        Expected fixed interval, in seconds, between consecutive data points.

    Returns
    -------
    list[tuple[int, int]]
        A list of `(missing_start, missing_end)` tuples, each representing an
        inclusive range of epochs where data points are missing at the
        expected cadence. If no gaps are found, the list is empty. If
        `existing_epochs` is empty and `end_epoch >= start_epoch`, a single
        range `(start_epoch, end_epoch)` is returned.
    """
    if end_epoch < start_epoch:
        return []

    if not existing_epochs:
        return [(start_epoch, end_epoch)]

    existing_epochs = sorted(existing_epochs)
    ranges: list[tuple[int, int]] = []
    current = start_epoch

    for epoch in existing_epochs:
        if epoch < current:
            continue
        if epoch > end_epoch:
            break

        if epoch > current:
            gap_end = epoch - interval_seconds
            if current <= gap_end:
                ranges.append((current, gap_end))
        current = epoch + interval_seconds

    if current <= end_epoch:
        ranges.append((current, end_epoch))

    return ranges
