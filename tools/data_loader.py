"""data_loader.py — load OHLCV data from MT5 CSV files OR Yahoo Finance.

Two entry points:
  * load_mt5_csv(path)            -- MT5-exported tab-separated CSV (preferred)
  * fetch_yahoo(symbol, ...)      -- live download via yfinance (fallback)
Both return a DataFrame with the same shape:
  index=datetime, columns=[open, high, low, close, volume, spread].
"""
from __future__ import annotations
import pandas as pd
from pathlib import Path


def load_mt5_csv(path: str | Path) -> pd.DataFrame:
    """Load an OHLCV CSV — auto-detects MT5 vs TradingView export format.

    MT5 format:         tab-separated, header `<DATE> <TIME> <OPEN> ...`
    TradingView format: comma-separated, header `time,open,high,low,close[,Volume]`
                        where `time` is a Unix epoch in seconds.

    Both return: DataFrame indexed by datetime with cols
                 open, high, low, close, volume, spread.
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        first = f.readline()

    if "<DATE>" in first or "<TIME>" in first or "\t" in first:
        # ---- MT5 tab-separated ----
        df = pd.read_csv(path, sep="\t")
        df.columns = [c.strip("<>").lower() for c in df.columns]
        df["dt"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M:%S")
        df = df.set_index("dt").drop(columns=["date", "time"])
        df = df.rename(columns={"tickvol": "volume"})
        keep = [c for c in ["open", "high", "low", "close", "volume", "spread"] if c in df.columns]
        df = df[keep]
        if "volume" not in df.columns: df["volume"] = 0
        if "spread" not in df.columns: df["spread"] = 0
        return df.sort_index()

    if "time" in first.lower() and "," in first:
        # ---- TradingView comma-separated ----
        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]
        if "time" not in df.columns:
            raise ValueError(f"TradingView format expected 'time' column, got: {list(df.columns)}")
        # Unix epoch seconds → datetime
        df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_localize(None)
        df = df.set_index("dt").drop(columns=["time"])
        if "volume" not in df.columns: df["volume"] = 0
        df["spread"] = 0
        df = df[["open", "high", "low", "close", "volume", "spread"]]
        return df.sort_index()

    raise ValueError(f"Unrecognised CSV format in {path}. "
                     f"First line: {first[:120]!r}")


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


# --------------- Yahoo Finance fallback ----------------------------------- #
_YAHOO_ALIAS = {
    # quant-lab friendly -> Yahoo ticker
    "XAUUSD":  "GC=F",       # gold futures (Yahoo has no spot XAU)
    "XAGUSD":  "SI=F",       # silver futures
    "EURUSD":  "EURUSD=X",
    "GBPUSD":  "GBPUSD=X",
    "USDJPY":  "USDJPY=X",
    "USDINR":  "USDINR=X",
    "BTCUSD":  "BTC-USD",
    "ETHUSD":  "ETH-USD",
    "SPX":     "^GSPC",
    "NASDAQ":  "^IXIC",
}

_INTERVAL_MAX_PERIOD = {
    # Yahoo's hard limits
    "1m":  "7d",
    "2m":  "60d",
    "5m":  "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "730d",
    "1h":  "730d",
    "1d":  "max",
    "1wk": "max",
    "1mo": "max",
}


def fetch_yahoo(symbol: str,
                interval: str = "5m",
                period: str | None = None,
                cache: bool = True,
                data_dir: str | Path | None = None) -> pd.DataFrame:
    """Download OHLCV from Yahoo Finance, return same shape as load_mt5_csv.

    symbol   : quant-lab friendly name (e.g. 'XAUUSD', 'EURUSD') OR raw Yahoo
               ticker ('GC=F', 'EURUSD=X', 'BTC-USD'). Auto-mapped via alias.
    interval : Yahoo interval — '1m','5m','15m','30m','1h','1d','1wk','1mo'.
    period   : Yahoo period — '7d','60d','730d','1y','5y','max'. Defaults to
               the max allowed for the chosen interval.
    cache    : if True, save the result under data/ as <symbol>_<interval>.csv.

    Raises ImportError if yfinance not installed, ValueError if no data.
    """
    try:
        import yfinance as yf
    except ImportError as e:
        raise ImportError("yfinance not installed. Run: pip install yfinance") from e

    ticker = _YAHOO_ALIAS.get(symbol.upper(), symbol)
    period = period or _INTERVAL_MAX_PERIOD.get(interval, "60d")

    df = yf.download(ticker, interval=interval, period=period,
                     progress=False, auto_adjust=False, prepost=False)
    if df is None or df.empty:
        raise ValueError(f"No data from Yahoo for '{symbol}' (ticker='{ticker}') "
                         f"interval={interval} period={period}")

    # yfinance returns MultiIndex columns when downloading
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]

    keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[keep].copy()
    if "volume" not in df.columns:
        df["volume"] = 0
    df["spread"] = 0          # Yahoo doesn't expose spread
    df.index.name = "dt"
    df = df.dropna(subset=["open", "high", "low", "close"]).sort_index()

    if cache:
        data_dir = Path(data_dir) if data_dir else (Path(__file__).resolve().parent.parent / "data")
        data_dir.mkdir(parents=True, exist_ok=True)
        safe = symbol.upper().replace("=", "_").replace("/", "_").replace("^", "_")
        out = data_dir / f"{safe}_{interval}_yahoo.csv"
        # save in MT5-style tab format so load_mt5_csv can re-read it next time
        out_df = df.reset_index()
        out_df["date"] = out_df["dt"].dt.strftime("%Y.%m.%d")
        out_df["time"] = out_df["dt"].dt.strftime("%H:%M:%S")
        out_df = out_df[["date", "time", "open", "high", "low", "close", "volume", "spread"]]
        out_df.insert(6, "tickvol", out_df["volume"])
        out_df = out_df.drop(columns=["volume"])
        out_df.columns = ["<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>",
                           "<CLOSE>", "<TICKVOL>", "<VOL>", "<SPREAD>"]
        out_df.insert(7, "<VOL>", 0)
        # de-dup the column we just inserted next to existing
        out_df = out_df.loc[:, ~out_df.columns.duplicated()]
        out_df.to_csv(out, sep="\t", index=False)
    return df


def load_data(source: str, interval: str = "5m") -> pd.DataFrame:
    """Smart loader: if source is an existing file path, read it as MT5 CSV.
    Otherwise treat source as a Yahoo symbol and fetch it. Never silently
    swallows errors — raises on both failure modes.
    """
    p = Path(source)
    if p.is_file():
        return load_mt5_csv(p)
    return fetch_yahoo(source, interval=interval)
