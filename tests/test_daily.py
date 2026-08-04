import numpy as np
import pandas as pd

from stock_prediction.daily import build_daily_brief
from stock_prediction.fundamentals import FundamentalSnapshot


def _history() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=220, freq="B")
    values = 20 + np.arange(220) * 0.04 + np.sin(np.arange(220) / 3)
    return pd.DataFrame(
        {"open": values, "high": values + 0.5, "low": values - 0.5, "close": values, "volume": 1_000_000},
        index=dates,
    )


def test_daily_brief_rejects_missing_fundamentals() -> None:
    brief = build_daily_brief({"TEST": _history()}, {})

    assert not brief.portfolio.allocations
    assert brief.fundamentals == {}


def test_daily_brief_keeps_fundamental_snapshot() -> None:
    snapshot = FundamentalSnapshot("TEST", pd.Timestamp("2025-12-31"), 20, 10, 10, 30, 2, 100, (), ())
    brief = build_daily_brief({"TEST": _history()}, {"TEST": snapshot})

    assert brief.fundamentals["TEST"] == snapshot
