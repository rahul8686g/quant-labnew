"""time_utils.py — session detection helpers (server-hour based)."""
from __future__ import annotations
import pandas as pd


SESSIONS = {
    "asian":   (1, 9),
    "london":  (8, 16),
    "newyork": (13, 21),
}


def in_session(timestamps: pd.DatetimeIndex, name: str) -> pd.Series:
    """Boolean mask: True when timestamp falls in the named session.
    Server-hour based (no time-zone conversion)."""
    start, end = SESSIONS[name.lower()]
    h = timestamps.hour
    if start < end:
        mask = (h >= start) & (h < end)
    else:  # wrap (e.g., 22-3)
        mask = (h >= start) | (h < end)
    return pd.Series(mask, index=timestamps)


def in_any_session(timestamps: pd.DatetimeIndex, names: list[str]) -> pd.Series:
    """OR-combine multiple session masks."""
    mask = pd.Series(False, index=timestamps)
    for n in names:
        mask = mask | in_session(timestamps, n)
    return mask
