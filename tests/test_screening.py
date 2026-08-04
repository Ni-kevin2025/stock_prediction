import numpy as np
import pandas as pd

from stock_prediction.screening import rank_candidates, score_candidate


def _history(values: np.ndarray) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=len(values), freq="B")
    return pd.DataFrame(
        {"open": values, "high": values + 0.5, "low": values - 0.5, "close": values, "volume": 2_000_000},
        index=dates,
    )


def test_candidate_scores_uptrend_above_downtrend() -> None:
    up = _history(np.linspace(10, 20, 90))
    down = _history(np.linspace(20, 10, 90))

    ranked = rank_candidates({"UP": up, "DOWN": down})

    assert ranked[0].symbol == "UP"
    assert ranked[0].score > ranked[1].score


def test_sell_candidate_score_is_capped() -> None:
    down = _history(np.linspace(20, 10, 90))

    candidate = score_candidate("DOWN", down)

    assert candidate.score <= 20
