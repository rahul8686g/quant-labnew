"""data_loader.py — load MT5-format CSV into a clean OHLCV DataFrame."""
from __future__ import annotations
import pandas as pd
from pathlib import Path


def load_mt5_csv(path: str | Path) -> pd.DataFrame:
    """Load an MT5-exported tab-separated CSV.
    Expected header: <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>
    Returns: DataFrame indexed by datetime with columns open, high, low, close, volume, spread.
    """
    df = pd.read_csv(path, sep="\t")
    df.columns = [c.strip("<>").lower() for c in df.columns]
    df["dt"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.set_index("dt").drop(columns=["date", "time"])
    df = df.rename(columns={"tickvol": "volume"})
    df = df[["open", "high", "low", "close", "volume", "spread"]]
    return df.sort_index()


def quality_check(df: pd.DataFrame, expected_freq_min: int = 5) -> dict:
    """Report data quality stats. expected_freq_min = bar period in minutes."""
    n = len(df)
    if n == 0:
        return {"rows": 0, "usable_pct": 0.0, "issue": "empty"}

    # OHLC sanity
    bad_ohlc = ((df.high < df.open) | (df.high < df.close)
                | (df.low > df.open) | (df.low > df.close)
                | (df.high < df.low)).sum()

    # gap detection
    gaps = df.index.to_series().diff().dropna()
    big_gaps = (gaps > pd.Timedelta(hours=72)).sum()  # ignore weekends < 72h

    dup = df.index.duplicated().sum()
    usable = n - bad_ohlc - dup
    return {
        "rows": int(n),
        "range": [str(df.index[0]), str(df.index[-1])],
        "duplicates": int(dup),
        "ohlc_violations": int(bad_ohlc),
        "large_gaps_gt_72h": int(big_gaps),
        "usable_pct": round(100.0 * usable / n, 2),
    }


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample to a higher timeframe. rule example: '15min', '1H', '4H'."""
    agg = {"open": "first", "high": "max", "low": "min",
           "close": "last", "volume": "sum", "spread": "mean"}
    return df.resample(rule, label="right", closed="right").agg(agg).dropna()
