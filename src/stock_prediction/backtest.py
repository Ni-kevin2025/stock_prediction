"""A small, transparent, no-lookahead single-asset backtester."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from stock_prediction.analysis import normalise_ohlcv
from stock_prediction.strategy import StrategyConfig, build_indicators


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    initial_cash: float
    final_equity: float
    total_return: float
    max_drawdown: float
    annualised_return: float | None
    sharpe_ratio: float | None
    win_rate: float | None


def run_backtest(
    frame: pd.DataFrame,
    config: StrategyConfig | None = None,
    initial_cash: float = 100_000.0,
    commission_bps: float = 5.0,
) -> BacktestResult:
    """Backtest strategy signals at the *next* day's open.

    The delayed execution is intentional: the strategy sees a day's close only
    after that session is complete. This prevents look-ahead bias.
    """

    if initial_cash <= 0:
        raise ValueError("initial_cash 必须为正数")
    config = config or StrategyConfig()
    data = build_indicators(frame, config)
    data = normalise_ohlcv(data)
    indicators = build_indicators(data, config)
    commission_rate = commission_bps / 10_000
    cash = initial_cash
    shares = 0.0
    entry_cost = 0.0
    trade_rows: list[dict[str, object]] = []
    curve_rows: list[dict[str, object]] = []

    for index in range(1, len(indicators)):
        today = indicators.iloc[index]
        yesterday = indicators.iloc[index - 1]
        date = indicators.index[index]
        open_price = float(today["open"])
        close_price = float(today["close"])
        action = "hold"

        mature = not pd.isna(yesterday["slow_sma"]) and not pd.isna(yesterday["rsi"])
        if shares > 0:
            stop_price = entry_cost * (1 - config.stop_loss_fraction)
            trend_broken = mature and float(yesterday["close"]) < float(yesterday["slow_sma"])
            overheated = mature and float(yesterday["rsi"]) >= config.sell_rsi
            if open_price <= stop_price or trend_broken or overheated:
                proceeds = shares * open_price * (1 - commission_rate)
                pnl = proceeds - (shares * entry_cost * (1 + commission_rate))
                trade_rows.append({"date": date, "side": "sell", "price": open_price, "shares": shares, "pnl": pnl})
                cash += proceeds
                shares = 0.0
                action = "sell"
        elif mature:
            uptrend = float(yesterday["close"]) > float(yesterday["fast_sma"]) > float(yesterday["slow_sma"])
            rsi = float(yesterday["rsi"])
            macd_confirmed = float(yesterday["macd"]) > float(yesterday["macd_signal"])
            if uptrend and config.buy_rsi_min <= rsi <= config.buy_rsi_max and macd_confirmed:
                budget = cash * config.max_position_fraction
                shares = budget / (open_price * (1 + commission_rate))
                cash -= shares * open_price * (1 + commission_rate)
                entry_cost = open_price
                trade_rows.append({"date": date, "side": "buy", "price": open_price, "shares": shares, "pnl": np.nan})
                action = "buy"

        equity = cash + shares * close_price
        curve_rows.append({"date": date, "cash": cash, "shares": shares, "close": close_price, "equity": equity, "action": action})

    equity_curve = pd.DataFrame(curve_rows).set_index("date")
    trades = pd.DataFrame(trade_rows, columns=["date", "side", "price", "shares", "pnl"])
    final_equity = float(equity_curve["equity"].iloc[-1]) if not equity_curve.empty else initial_cash
    return _summarise(equity_curve, trades, initial_cash, final_equity)


def _summarise(curve: pd.DataFrame, trades: pd.DataFrame, initial_cash: float, final_equity: float) -> BacktestResult:
    total_return = final_equity / initial_cash - 1
    if curve.empty:
        return BacktestResult(curve, trades, initial_cash, final_equity, total_return, 0.0, None, None, None)
    drawdown = curve["equity"] / curve["equity"].cummax() - 1
    daily_returns = curve["equity"].pct_change().dropna()
    years = len(curve) / 252
    annualised = (final_equity / initial_cash) ** (1 / years) - 1 if years > 0 and final_equity > 0 else None
    sharpe = None
    if len(daily_returns) > 1 and daily_returns.std(ddof=1) > 0:
        sharpe = float(np.sqrt(252) * daily_returns.mean() / daily_returns.std(ddof=1))
    completed = trades.loc[trades["side"] == "sell", "pnl"] if not trades.empty else pd.Series(dtype=float)
    win_rate = float((completed > 0).mean()) if not completed.empty else None
    return BacktestResult(curve, trades, initial_cash, final_equity, total_return, float(drawdown.min()), annualised, sharpe, win_rate)
