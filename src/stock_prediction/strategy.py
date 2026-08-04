"""Rule-based decision and risk agents for one stock at a time.

Rules are explicit configuration rather than model guesses, which makes every
recommendation and backtest reproducible. The output is decision support only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from stock_prediction.analysis import _rsi, normalise_ohlcv


class Action(StrEnum):
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    WAIT = "wait"


@dataclass(frozen=True)
class StrategyConfig:
    fast_window: int = 20
    slow_window: int = 60
    rsi_window: int = 14
    buy_rsi_min: float = 50.0
    buy_rsi_max: float = 70.0
    sell_rsi: float = 75.0
    max_position_fraction: float = 0.20
    stop_loss_fraction: float = 0.08

    def __post_init__(self) -> None:
        if not 0 < self.fast_window < self.slow_window:
            raise ValueError("fast_window 必须小于 slow_window，且两者均为正数")
        if not 0 < self.max_position_fraction <= 1:
            raise ValueError("max_position_fraction 必须在 (0, 1] 之间")
        if not 0 < self.stop_loss_fraction < 1:
            raise ValueError("stop_loss_fraction 必须在 (0, 1) 之间")


@dataclass(frozen=True)
class Decision:
    symbol: str
    as_of: pd.Timestamp
    action: Action
    target_position_fraction: float
    stop_loss_price: float | None
    confidence: str
    reasons: tuple[str, ...]
    risk_notes: tuple[str, ...]


def build_indicators(frame: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    """Return price history plus only indicators known at each row's close."""

    data = normalise_ohlcv(frame)
    data["fast_sma"] = data["close"].rolling(config.fast_window, min_periods=config.fast_window).mean()
    data["slow_sma"] = data["close"].rolling(config.slow_window, min_periods=config.slow_window).mean()
    data["rsi"] = _rsi(data["close"], config.rsi_window)
    data["macd"] = data["close"].ewm(span=12, adjust=False).mean() - data["close"].ewm(span=26, adjust=False).mean()
    data["macd_signal"] = data["macd"].ewm(span=9, adjust=False).mean()
    return data


def decide(symbol: str, frame: pd.DataFrame, config: StrategyConfig | None = None) -> Decision:
    """Create the latest rule-based buy/hold/sell/wait decision.

    A buy needs an established uptrend, non-extreme RSI, and MACD confirmation.
    A sell is triggered by a broken trend or overheated RSI. Stop loss is returned
    as a mandatory risk boundary for a hypothetical new position.
    """

    config = config or StrategyConfig()
    data = build_indicators(frame, config)
    row = data.iloc[-1]
    as_of = data.index[-1]
    if pd.isna(row["slow_sma"]) or pd.isna(row["rsi"]):
        return Decision(
            symbol=symbol.upper(), as_of=as_of, action=Action.WAIT,
            target_position_fraction=0.0, stop_loss_price=None, confidence="low",
            reasons=("可用历史数据不足，无法计算完整的长期趋势。",),
            risk_notes=("继续观察，补足至少 60 个交易日数据后再评估。",),
        )

    price = float(row["close"])
    fast = float(row["fast_sma"])
    slow = float(row["slow_sma"])
    rsi = float(row["rsi"])
    macd_confirmed = float(row["macd"]) > float(row["macd_signal"])
    uptrend = price > fast > slow
    reasons: list[str] = [f"收盘价 {price:.2f}，20 日均线 {fast:.2f}，60 日均线 {slow:.2f}。"]
    risk_notes = ["单一标的目标仓位受限于总资金的 20%，不可满仓。", "该结果是规则信号，不是收益承诺或交易指令。"]

    if price < slow:
        reasons.append("收盘价跌破长期均线，趋势条件失效。")
        action = Action.SELL
        target = 0.0
        confidence = "medium"
    elif rsi >= config.sell_rsi:
        reasons.append(f"RSI({config.rsi_window}) 为 {rsi:.1f}，动量过热。")
        action = Action.SELL
        target = 0.0
        confidence = "low"
    elif uptrend and config.buy_rsi_min <= rsi <= config.buy_rsi_max and macd_confirmed:
        reasons.append("趋势、RSI 区间和 MACD 同时满足入场过滤条件。")
        action = Action.BUY
        target = config.max_position_fraction
        confidence = "medium"
    elif uptrend:
        reasons.append("趋势向上，但动量过滤条件尚未全部确认。")
        action = Action.HOLD
        target = config.max_position_fraction
        confidence = "low"
    else:
        reasons.append("尚未形成可执行的趋势入场条件。")
        action = Action.WAIT
        target = 0.0
        confidence = "low"

    stop_loss = round(price * (1 - config.stop_loss_fraction), 2) if action in {Action.BUY, Action.HOLD} else None
    if stop_loss is not None:
        risk_notes.insert(0, f"假设建仓后的初始止损参考价：{stop_loss:.2f}（距当前价 {config.stop_loss_fraction:.0%}）。")
    return Decision(symbol.upper(), as_of, action, target, stop_loss, confidence, tuple(reasons), tuple(risk_notes))
