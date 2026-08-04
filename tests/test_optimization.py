import numpy as np
import pandas as pd

from stock_prediction.optimization import default_configurations, optimise_out_of_sample, select_on_training


def _history() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=260, freq="B")
    values = 20 + np.linspace(0, 10, len(dates)) + np.sin(np.arange(len(dates)) / 3)
    return pd.DataFrame(
        {"open": values, "high": values + 0.5, "low": values - 0.5, "close": values, "volume": 1_000_000},
        index=dates,
    )


def test_selection_returns_only_predeclared_configuration() -> None:
    selected, evaluations = select_on_training(_history().iloc[:180])

    assert selected.config in default_configurations()
    assert len(evaluations) == len(default_configurations())


def test_optimisation_keeps_later_period_out_of_selection() -> None:
    data = _history()
    result = optimise_out_of_sample(data)

    assert result.split_date == data.index[int(len(data) * 0.60)]
    assert result.test_result.equity_curve.index.min() >= result.split_date
