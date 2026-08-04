"""Deterministic technical analysis used by the research agent.

The module deliberately keeps indicator calculation separate from data retrieval so
the calculations are testable and every report can be reproduced from its input.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}


@dataclass(frozen=True)
class AnalysisResult:
    """Latest values and an explanatory, non-trading research view."""

    symbol: str
    as_of: pd.Timestamp
    close: float
    sma_20: float | None
    sma_60: float | None
    rsi_14: float | None
    macd: float | None
    macd_signal: float | None
    volume_ratio_20: float | None
    trend: str
    momentum: str
    observations: tuple[str, ...]
    warnings: tuple[str, ...]


def normalise_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and standardise an OHLCV frame without mutating the caller's data."""

    data = frame.copy()
    data.columns = [str(column).lower() for column in data.columns]
    missing = REQUIRED_COLUMNS.difference(data.columns)
    if missing:
        raise ValueError(f"行情数据缺少必要列: {', '.join(sorted(missing))}")
    if data.empty:
        raise ValueError("行情数据为空")

    data.index = pd.to_datetime(data.index)
    data = data.sort_index()
    data = data.loc[:, ["open", "high", "low", "close", "volume"]]
    for column in data.columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["close"])
    if data.empty:
        raise ValueError("没有可用的收盘价数据")
    return data


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    losses = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    relative_strength = gains / losses
    rsi = 100 - (100 / (1 + relative_strength))
    # A period with gains and no losses is conventionally treated as RSI 100;
    # a completely flat period remains undefined rather than inventing momentum.
    return rsi.mask((losses == 0) & (gains > 0), 100.0)


def analyse_price_history(symbol: str, frame: pd.DataFrame) -> AnalysisResult:
    """Calculate a compact, explainable technical research snapshot.

    This returns analysis observations only. It is not a buy/sell recommendation.
    """

    data = normalise_ohlcv(frame)
    close = data["close"]
    sma_20 = close.rolling(20, min_periods=20).mean()
    sma_60 = close.rolling(60, min_periods=60).mean()
    rsi_14 = _rsi(close)
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    volume_average = data["volume"].rolling(20, min_periods=20).mean()

    latest = data.index[-1]
    latest_close = float(close.iloc[-1])
    latest_sma_20 = _optional_float(sma_20.iloc[-1])
    latest_sma_60 = _optional_float(sma_60.iloc[-1])
    latest_rsi = _optional_float(rsi_14.iloc[-1])
    latest_macd = _optional_float(macd.iloc[-1])
    latest_signal = _optional_float(macd_signal.iloc[-1])
    latest_volume_ratio = _optional_float((data["volume"] / volume_average).iloc[-1])

    observations: list[str] = []
    warnings: list[str] = ["本报告仅供研究参考，不构成投资建议或交易指令。"]
    if len(data) < 60:
        warnings.append("历史数据少于 60 个交易日，长期均线结论不完整。")

    trend = "数据不足"
    if latest_sma_20 is not None and latest_sma_60 is not None:
        if latest_close > latest_sma_20 > latest_sma_60:
            trend = "上行"
            observations.append("收盘价位于 20 日和 60 日均线上方。")
        elif latest_close < latest_sma_20 < latest_sma_60:
            trend = "下行"
            observations.append("收盘价位于 20 日和 60 日均线下方。")
        else:
            trend = "震荡"
            observations.append("价格与中短期均线交错，趋势不明确。")

    momentum = "数据不足"
    if latest_rsi is not None:
        if latest_rsi >= 70:
            momentum = "偏热"
            observations.append(f"RSI(14) 为 {latest_rsi:.1f}，处于偏热区间。")
        elif latest_rsi <= 30:
            momentum = "偏弱"
            observations.append(f"RSI(14) 为 {latest_rsi:.1f}，处于偏弱区间。")
        else:
            momentum = "中性"
            observations.append(f"RSI(14) 为 {latest_rsi:.1f}，未进入极端区间。")
    if latest_macd is not None and latest_signal is not None:
        relation = "上方" if latest_macd >= latest_signal else "下方"
        observations.append(f"MACD 线位于信号线{relation}。")
    if latest_volume_ratio is not None:
        observations.append(f"当日成交量为 20 日均量的 {latest_volume_ratio:.2f} 倍。")

    return AnalysisResult(
        symbol=symbol.upper(),
        as_of=latest,
        close=latest_close,
        sma_20=latest_sma_20,
        sma_60=latest_sma_60,
        rsi_14=latest_rsi,
        macd=latest_macd,
        macd_signal=latest_signal,
        volume_ratio_20=latest_volume_ratio,
        trend=trend,
        momentum=momentum,
        observations=tuple(observations),
        warnings=tuple(warnings),
    )


def _optional_float(value: object) -> float | None:
    return None if pd.isna(value) else float(value)
