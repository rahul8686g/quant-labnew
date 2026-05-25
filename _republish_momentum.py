"""one-shot: regenerate Pine for the validated momentum_v1 with session filter
and publish to output/<symbol>_<tf>_<strategy>_<timestamp>/."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from report import export_pine
from tools.publish import publish_winner

# Winning params (from auto-refine attempt 2 result)
PARAMS = {
    "ema_filter":    100,
    "roc_period":    11,
    "roc_threshold": 1.0159,
    "rsi_period":    14,
    "rsi_strength":  59.766,
    "atr_period":    14,
    "atr_sl_mult":   1.9325,
    "atr_tp_mult":   3.0,
    "risk_pct":      0.5,
}
METRICS = {
    "net_profit":    2227.27,
    "return_pct":    22.27,
    "profit_factor": 1.47,
    "max_dd_pct":    5.73,
    "win_rate":      50.0,
    "trades":        150,
    "sharpe":        1.92,
}

# Regenerate Pine with the new session-filter template
pine_dst = HERE / "report" / "validated_momentum_v1.pine"
export_pine(pine_dst, name="momentum_v1", symbol="XAUUSD",
            timeframe="M30", params=PARAMS, family="momentum")
print(f"Pine regenerated with session filter: {pine_dst}")

# Publish to output folder
out_dir = publish_winner(
    project_root  = HERE,
    symbol        = "XAUUSD",
    timeframe     = "M30",
    strategy_name = "momentum_v1",
    family        = "momentum",
    params        = PARAMS,
    metrics       = METRICS,
    html_path     = str(HERE / "report" / "validated_momentum_v1.html"),
    pdf_path      = str(HERE / "report" / "validated_momentum_v1.pdf"),
    mq5_path      = None,                       # momentum family MQ5 not yet supported
    pine_path     = str(pine_dst),
)
print(f"Published to: {out_dir}")
