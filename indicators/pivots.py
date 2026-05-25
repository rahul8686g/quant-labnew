"""Pivot point indicators — Standard, Camarilla, Woodie, Fibonacci.
All computed from the PREVIOUS session/day's H, L, C — no look-ahead.
"""
from __future__ import annotations
import pandas as pd


def _daily_hlc(df: pd.DataFrame) -> pd.DataFrame:
    g = df.resample("D")
    return pd.DataFrame({
        "h": g["high"].max().shift(1),
        "l": g["low"].min().shift(1),
        "c": g["close"].last().shift(1),
    })


def standard_pivots(df: pd.DataFrame) -> pd.DataFrame:
    """Classic floor pivots. Cols: pp, r1, r2, r3, s1, s2, s3 (broadcast to df index)."""
    d = _daily_hlc(df)
    pp = (d["h"] + d["l"] + d["c"]) / 3
    r1 = 2 * pp - d["l"]; s1 = 2 * pp - d["h"]
    r2 = pp + (d["h"] - d["l"]); s2 = pp - (d["h"] - d["l"])
    r3 = d["h"] + 2 * (pp - d["l"]); s3 = d["l"] - 2 * (d["h"] - pp)
    out = pd.DataFrame({"pp": pp, "r1": r1, "r2": r2, "r3": r3,
                         "s1": s1, "s2": s2, "s3": s3})
    return out.reindex(df.index, method="ffill")


def camarilla_pivots(df: pd.DataFrame) -> pd.DataFrame:
    """Camarilla — popular intraday levels."""
    d = _daily_hlc(df); rng = d["h"] - d["l"]
    out = pd.DataFrame({
        "r4": d["c"] + rng * 1.1 / 2, "r3": d["c"] + rng * 1.1 / 4,
        "r2": d["c"] + rng * 1.1 / 6, "r1": d["c"] + rng * 1.1 / 12,
        "s1": d["c"] - rng * 1.1 / 12, "s2": d["c"] - rng * 1.1 / 6,
        "s3": d["c"] - rng * 1.1 / 4,  "s4": d["c"] - rng * 1.1 / 2,
    })
    return out.reindex(df.index, method="ffill")


def woodie_pivots(df: pd.DataFrame) -> pd.DataFrame:
    """Woodie — weights close more heavily."""
    d = _daily_hlc(df)
    pp = (d["h"] + d["l"] + 2 * d["c"]) / 4
    r1 = 2 * pp - d["l"]; s1 = 2 * pp - d["h"]
    r2 = pp + (d["h"] - d["l"]); s2 = pp - (d["h"] - d["l"])
    out = pd.DataFrame({"pp": pp, "r1": r1, "r2": r2, "s1": s1, "s2": s2})
    return out.reindex(df.index, method="ffill")


def fib_pivots(df: pd.DataFrame) -> pd.DataFrame:
    """Fibonacci pivot points."""
    d = _daily_hlc(df)
    pp = (d["h"] + d["l"] + d["c"]) / 3
    rng = d["h"] - d["l"]
    out = pd.DataFrame({
        "pp": pp,
        "r1": pp + 0.382 * rng, "r2": pp + 0.618 * rng, "r3": pp + 1.000 * rng,
        "s1": pp - 0.382 * rng, "s2": pp - 0.618 * rng, "s3": pp - 1.000 * rng,
    })
    return out.reindex(df.index, method="ffill")
