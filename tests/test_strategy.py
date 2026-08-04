import numpy as np
import pandas as pd

from stock_prediction.backtest import run_backtest
from stock_prediction.strategy import Action, StrategyConfig, decide


def _prices(values: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=len(values), freq="B")
    close = np.array(values, dtype=float)
    return pd.DataFrame(
        {"open": close, "high": close + 0.5, "low": close - 0.5, "close": close, "volume": 1_000_000},
        index=dates,
    )


def test_decision_buys_on_confirmed_uptrend() -> None:
    prices = list(np.linspace(10, 25, 90))
    config = StrategyConfig(buy_rsi_max=100, sell_rsi=101)
    decision = decide("TEST", _prices(prices), config)

    assert decision.action == Action.BUY
    assert decision.target_position_fraction == 0.20
    assert decision.stop_loss_price is not None


def test_decision_sells_when_price_breaks_long_average() -> None:
    prices = list(np.linspace(10, 25, 80)) + list(np.linspace(24, 10, 15))
    decision = decide("TEST", _prices(prices))

    assert decision.action == Action.SELL
    assert decision.target_position_fraction == 0.0


def test_backtest_records_equity_and_executes_only_after_signal_day() -> None:
    prices = list(np.linspace(10, 25, 90)) + list(np.linspace(24, 15, 30))
    config = StrategyConfig(buy_rsi_max=100, sell_rsi=101)
    result = run_backtest(_prices(prices), config)

    assert not result.equity_curve.empty
    assert (result.trades["side"] == "buy").any()
    first_buy = result.trades.loc[result.trades["side"] == "buy", "date"].iloc[0]
    # The slow indicator is first available on the 60th row; execution is next day.
    assert first_buy >= pd.Timestamp("2025-03-26")
