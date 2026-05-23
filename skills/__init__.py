"""Strategy templates. Each template is a Strategy subclass with a `params` dict."""
from .trend_template import TrendStrategy
from .meanrev_template import MeanRevStrategy
from .breakout_template import BreakoutStrategy

__all__ = ["TrendStrategy", "MeanRevStrategy", "BreakoutStrategy"]
