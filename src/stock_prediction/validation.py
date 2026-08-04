"""Benchmarking and time-ordered out-of-sample validation for strategies."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stock_prediction.analysis import normalise_ohlcv
from stock_prediction.backtest import BacktestResult, run_backtest
from stock_prediction.strategy import StrategyConfig


@dataclass(frozen=True)
class ValidationResult:
    train: BacktestResult
    test: BacktestResult
    benchmark: BacktestResult
    split_date: pd.Timestamp
    strategy_excess_return: float
    passed_benchmark: bool


def buy_and_hold(
    frame: pd.DataFrame,
    initial_cash: float = 100_000.0,
    commission_bps: float = 5.0,
) -> BacktestResult:
    """Return a fee-aware buy-and-hold baseline for the same OHLCV input."""

    data = normalise_ohlcv(frame)
    rate = commission_bps / 10_000
    entry_price = float(data["open"].iloc[0])
    shares = initial_cash / (entry_price * (1 + rate))
    cash = initial_cash - shares * entry_price * (1 + rate)
    curve = pd.DataFrame(
        {
            "cash": cash,
            "shares": shares,
            "close": data["close"],
            "equity": cash + shares * data["close"],
            "action": "hold",
        },
        index=data.index,
    )
    curve.index.name = "date"
    trades = pd.DataFrame(
        [{"date": data.index[0], "side": "buy", "price": entry_price, "shares": shares, "pnl": float("nan")}]
    )
    from stock_prediction.backtest import _summarise  # Keep metric definitions identical.

    return _summarise(curve, trades, initial_cash, float(curve["equity"].iloc[-1]))


def validate_out_of_sample(
    frame: pd.DataFrame,
    config: StrategyConfig | None = None,
    training_fraction: float = 0.60,
    initial_cash: float = 100_000.0,
) -> ValidationResult:
    """Evaluate a fixed rule on a later, untouched chronological period.

    Parameters are *not* optimised on the test period. A strategy only passes this
    simple gate when its test return is better than buy-and-hold on the same dates.
    """

    if not 0.5 <= training_fraction < 0.9:
        raise ValueError("training_fraction 必须在 [0.5, 0.9) 之间")
    data = normalise_ohlcv(frame)
    split = int(len(data) * training_fraction)
    if split < 70 or len(data) - split < 70:
        raise ValueError("样本外验证至少需要训练段和测试段各 70 个交易日")
    train_data = data.iloc[:split]
    test_data = data.iloc[split:]
    train = run_backtest(train_data, config, initial_cash)
    test = run_backtest(test_data, config, initial_cash)
    benchmark = buy_and_hold(test_data, initial_cash)
    excess = test.total_return - benchmark.total_return
    return ValidationResult(
        train=train,
        test=test,
        benchmark=benchmark,
        split_date=test_data.index[0],
        strategy_excess_return=excess,
        passed_benchmark=excess > 0,
    )
