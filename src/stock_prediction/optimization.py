"""Chronological strategy-selection agent with an untouched test period."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stock_prediction.analysis import normalise_ohlcv
from stock_prediction.backtest import BacktestResult, run_backtest
from stock_prediction.strategy import StrategyConfig
from stock_prediction.validation import buy_and_hold


@dataclass(frozen=True)
class StrategyEvaluation:
    config: StrategyConfig
    result: BacktestResult
    score: float


@dataclass(frozen=True)
class OptimisationResult:
    split_date: pd.Timestamp
    selected: StrategyEvaluation
    training_evaluations: tuple[StrategyEvaluation, ...]
    test_result: BacktestResult
    benchmark: BacktestResult

    @property
    def test_excess_return(self) -> float:
        return self.test_result.total_return - self.benchmark.total_return


def default_configurations() -> tuple[StrategyConfig, ...]:
    """A deliberately small, pre-declared search space to limit data mining."""

    return (
        StrategyConfig(fast_window=10, slow_window=40, buy_rsi_min=45),
        StrategyConfig(fast_window=10, slow_window=60, buy_rsi_min=45),
        StrategyConfig(fast_window=20, slow_window=60, buy_rsi_min=45),
        StrategyConfig(fast_window=20, slow_window=60, buy_rsi_min=50),
    )


def select_on_training(
    training_frame: pd.DataFrame, configurations: tuple[StrategyConfig, ...] | None = None
) -> tuple[StrategyEvaluation, tuple[StrategyEvaluation, ...]]:
    """Choose one configuration using only chronological training data."""

    evaluations = []
    for config in configurations or default_configurations():
        result = run_backtest(training_frame, config)
        # A simple risk-adjusted score; no data from the later test period enters it.
        score = result.total_return + result.max_drawdown * 0.5
        evaluations.append(StrategyEvaluation(config, result, score))
    ranked = tuple(sorted(evaluations, key=lambda evaluation: evaluation.score, reverse=True))
    return ranked[0], ranked


def optimise_out_of_sample(
    frame: pd.DataFrame,
    configurations: tuple[StrategyConfig, ...] | None = None,
    training_fraction: float = 0.60,
    initial_cash: float = 100_000.0,
) -> OptimisationResult:
    """Select on training data then measure one untouched later test period."""

    data = normalise_ohlcv(frame)
    if not 0.5 <= training_fraction < 0.9:
        raise ValueError("training_fraction 必须在 [0.5, 0.9) 之间")
    split = int(len(data) * training_fraction)
    if split < 70 or len(data) - split < 70:
        raise ValueError("优化验证至少需要训练段和测试段各 70 个交易日")
    train_data = data.iloc[:split]
    test_data = data.iloc[split:]
    selected, evaluations = select_on_training(train_data, configurations)
    test_result = run_backtest(test_data, selected.config, initial_cash)
    benchmark = buy_and_hold(test_data, initial_cash)
    return OptimisationResult(test_data.index[0], selected, evaluations, test_result, benchmark)
