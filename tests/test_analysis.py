import numpy as np
import pandas as pd

from stock_prediction.analysis import analyse_price_history
from stock_prediction.reporting import render_markdown


def _sample_prices() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=80, freq="B")
    close = np.linspace(10, 20, len(dates))
    return pd.DataFrame(
        {
            "Open": close - 0.2,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": np.full(len(dates), 1_000_000),
        },
        index=dates,
    )


def test_analysis_of_rising_prices_reports_uptrend() -> None:
    result = analyse_price_history("000001.SZ", _sample_prices())

    assert result.trend == "上行"
    assert result.sma_20 is not None
    assert result.sma_60 is not None
    assert "不构成投资建议" in result.warnings[0]


def test_report_contains_symbol_and_as_of_date() -> None:
    result = analyse_price_history("000001.SZ", _sample_prices())
    report = render_markdown(result)

    assert "# 000001.SZ 研究快照" in report
    assert "数据截至：2026-04-22" in report
