import numpy as np
import pandas as pd

from stock_prediction.validation import buy_and_hold, validate_out_of_sample


def _history(periods: int = 220) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=periods, freq="B")
    close = 20 + np.sin(np.arange(periods) / 4) + np.arange(periods) * 0.03
    return pd.DataFrame(
        {"open": close, "high": close + 0.5, "low": close - 0.5, "close": close, "volume": 1_000_000},
        index=dates,
    )


def test_buy_and_hold_tracks_same_period_equity() -> None:
    result = buy_and_hold(_history())

    assert result.final_equity > result.initial_cash
    assert len(result.trades) == 1


def test_validation_uses_later_period_as_test_set() -> None:
    data = _history()
    result = validate_out_of_sample(data)

    assert result.split_date == data.index[int(len(data) * 0.60)]
    assert result.test.equity_curve.index.min() >= result.split_date
