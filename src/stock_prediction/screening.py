"""Candidate-screening agent for a user-supplied stock universe."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from stock_prediction.strategy import Action, Decision, StrategyConfig, build_indicators, decide


@dataclass(frozen=True)
class Candidate:
    symbol: str
    score: int
    decision: Decision
    close: float
    rsi: float | None
    rationale: tuple[str, ...]


def score_candidate(symbol: str, frame: pd.DataFrame, config: StrategyConfig | None = None) -> Candidate:
    """Score one stock with transparent trend, momentum and risk components."""

    config = config or StrategyConfig()
    decision = decide(symbol, frame, config)
    indicators = build_indicators(frame, config)
    row = indicators.iloc[-1]
    close = float(row["close"])
    rsi = None if pd.isna(row["rsi"]) else float(row["rsi"])
    score = 0
    rationale: list[str] = []
    if not pd.isna(row["slow_sma"]) and close > float(row["fast_sma"]) > float(row["slow_sma"]):
        score += 45
        rationale.append("价格位于 20/60 日均线上方（45 分）。")
    elif not pd.isna(row["slow_sma"]) and close < float(row["slow_sma"]):
        rationale.append("价格低于 60 日均线（0 分）。")
    if not pd.isna(row["macd"]) and float(row["macd"]) > float(row["macd_signal"]):
        score += 25
        rationale.append("MACD 高于信号线（25 分）。")
    if rsi is not None and config.buy_rsi_min <= rsi <= config.buy_rsi_max:
        score += 20
        rationale.append(f"RSI 位于策略入场区间（20 分）。")
    elif rsi is not None and rsi >= config.sell_rsi:
        rationale.append("RSI 过热，不增加动量分数。")
    volume_mean = indicators["volume"].rolling(20, min_periods=20).mean().iloc[-1]
    if not pd.isna(volume_mean) and float(row["volume"]) >= float(volume_mean):
        score += 10
        rationale.append("成交量不低于 20 日均量（10 分）。")
    if decision.action == Action.SELL:
        score = min(score, 20)
        rationale.append("卖出风控条件触发，分数上限设为 20。")
    return Candidate(symbol.upper(), score, decision, close, rsi, tuple(rationale))


def rank_candidates(histories: Mapping[str, pd.DataFrame], config: StrategyConfig | None = None) -> list[Candidate]:
    """Rank pre-fetched histories without fetching network data inside scoring."""

    candidates = [score_candidate(symbol, history, config) for symbol, history in histories.items()]
    return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.symbol))
