"""Manual A-share order-plan generation with cash and risk constraints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from stock_prediction.account import Holding, TradingProfile
from stock_prediction.daily import DailyBrief
from stock_prediction.strategy import Action


@dataclass(frozen=True)
class PlannedOrder:
    symbol: str
    action: str
    quantity: int
    limit_low: float | None
    limit_high: float | None
    stop_loss: float | None
    estimated_value: float
    reason: str


@dataclass(frozen=True)
class TradePlan:
    total_assets_estimate: float
    planned_orders: tuple[PlannedOrder, ...]
    notes: tuple[str, ...]


def build_trade_plan(
    brief: DailyBrief, profile: TradingProfile, live_prices: Mapping[str, float] | None = None
) -> TradePlan:
    """Create *manual* A-share orders from qualified candidates and holdings.

    Prices are derived from the latest daily close, so they are planning ranges,
    not real-time executable quotes. The user must check the live quote in
    Tonghuashun before manually placing any order.
    """

    candidates = {candidate.symbol: candidate for candidate in brief.candidates}
    live_prices = {key.upper(): value for key, value in (live_prices or {}).items()}
    holding_map = {holding.symbol.upper(): holding for holding in profile.holdings}
    total_assets = profile.available_cash + sum(
        holding.shares * live_prices.get(holding.symbol.upper(), candidates.get(holding.symbol.upper(), _holding_candidate_stub(holding)).close)
        for holding in profile.holdings
    )
    orders: list[PlannedOrder] = []

    # Existing holdings always receive a risk-review decision before new buys.
    for symbol, holding in holding_map.items():
        candidate = candidates.get(symbol)
        if candidate is None:
            orders.append(PlannedOrder(symbol, "REVIEW", 0, None, None, None, 0.0, "未获取到当前行情，需在同花顺人工核对持仓。"))
            continue
        current_price = live_prices.get(symbol, candidate.close)
        stop = round(holding.average_cost * 0.92, 2)
        if current_price <= stop:
            orders.append(_sell_order(holding, current_price, stop, "当前实时价格触及基于持仓成本的 8% 止损线。"))
        elif candidate.decision.action == Action.SELL:
            orders.append(_sell_order(holding, current_price, stop, "策略趋势/动量卖出条件触发。"))
        else:
            orders.append(PlannedOrder(symbol, "HOLD", holding.shares, None, None, stop, holding.shares * current_price, "未触发卖出或止损；继续跟踪。"))

    remaining_cash = profile.available_cash
    allocated_symbols = {allocation.symbol for allocation in brief.portfolio.allocations}
    for allocation in brief.portfolio.allocations:
        if allocation.symbol in holding_map:
            continue
        candidate = candidates[allocation.symbol]
        entry = live_prices.get(allocation.symbol, allocation.reference_price)
        stop = allocation.stop_loss_price
        low, high = round(entry * 0.997, 2), round(entry * 1.003, 2)
        risk_per_share = max(entry - stop, 0.01)
        risk_budget = total_assets * profile.risk_per_trade
        max_by_risk = int(risk_budget / risk_per_share / 100) * 100
        max_by_position = int((total_assets * profile.max_position_fraction) / entry / 100) * 100
        max_by_cash = int(remaining_cash / entry / 100) * 100
        quantity = min(max_by_risk, max_by_position, max_by_cash)
        if quantity < 100:
            orders.append(PlannedOrder(allocation.symbol, "WAIT", 0, low, high, stop, 0.0, "现金或风险预算不足以买入 1 手（100 股）。"))
            continue
        value = quantity * entry
        remaining_cash -= value
        orders.append(PlannedOrder(
            allocation.symbol,
            "BUY",
            quantity,
            low,
            high,
            stop,
            value,
            "通过技术、样本外和基本面资格门槛；数量受单笔风险、仓位和现金三重限制。",
        ))
    if not allocated_symbols:
        orders.append(PlannedOrder("—", "CASH", 0, None, None, None, 0.0, "没有股票通过全部资格门槛，今日不新增仓位。"))
    notes = (
        "计划价格范围基于最新日线收盘价，不是实时盘口价格。下单前必须在同花顺核对实时价格、涨跌停、停牌和可用资金。",
        "所有买入数量均按 A 股 100 股整手计算；卖出数量使用你录入的持仓数量。",
        "该计划仅供你在平安证券/同花顺手工复核和下单，不会连接或控制交易账户。",
    )
    return TradePlan(total_assets, tuple(orders), notes)


def _sell_order(holding: Holding, close: float, stop: float, reason: str) -> PlannedOrder:
    return PlannedOrder(holding.symbol.upper(), "SELL", holding.shares, round(close * 0.997, 2), round(close * 1.003, 2), stop, holding.shares * close, reason)


@dataclass(frozen=True)
class _HoldingCandidateStub:
    close: float


def _holding_candidate_stub(holding: Holding) -> _HoldingCandidateStub:
    return _HoldingCandidateStub(holding.average_cost)
