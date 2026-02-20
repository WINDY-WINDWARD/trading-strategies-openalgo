from __future__ import annotations

from datetime import datetime, timezone


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
        expected cadence. Weekend slots (Saturday and Sunday, UTC) are ignored
        and never returned as missing ranges. If no gaps are found, the list
        is empty.
    """
    if end_epoch < start_epoch or interval_seconds <= 0:
        return []

    existing_epoch_set = {
        epoch
        for epoch in existing_epochs
        if start_epoch <= epoch <= end_epoch and not _is_weekend_epoch(epoch)
    }
    ranges: list[tuple[int, int]] = []
    gap_start: int | None = None
    previous_missing: int | None = None

    epoch = start_epoch
    while epoch <= end_epoch:
        if not _is_weekend_epoch(epoch) and epoch not in existing_epoch_set:
            if gap_start is None:
                gap_start = epoch
            elif previous_missing is not None and epoch != previous_missing + interval_seconds:
                ranges.append((gap_start, previous_missing))
                gap_start = epoch
            previous_missing = epoch
        elif gap_start is not None and previous_missing is not None:
            ranges.append((gap_start, previous_missing))
            gap_start = None
            previous_missing = None

        epoch += interval_seconds

    if gap_start is not None and previous_missing is not None:
        ranges.append((gap_start, previous_missing))

    return ranges


def _is_weekend_epoch(epoch: int) -> bool:
    weekday = datetime.fromtimestamp(epoch, tz=timezone.utc).weekday()
    return weekday >= 5
