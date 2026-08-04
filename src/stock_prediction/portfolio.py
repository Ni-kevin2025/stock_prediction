"""Portfolio-construction agent with explicit qualification gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from stock_prediction.screening import Candidate
from stock_prediction.strategy import Action


@dataclass(frozen=True)
class Allocation:
    symbol: str
    score: int
    weight: float
    capital: float
    reference_price: float
    stop_loss_price: float


@dataclass(frozen=True)
class PortfolioProposal:
    initial_capital: float
    allocations: tuple[Allocation, ...]
    unallocated_cash: float
    excluded: tuple[str, ...]


def propose_portfolio(
    candidates: list[Candidate],
    validation_passes: Mapping[str, bool],
    fundamental_scores: Mapping[str, int] | None = None,
    initial_capital: float = 100_000.0,
    max_positions: int = 5,
    max_position_fraction: float = 0.20,
    min_score: int = 70,
    min_fundamental_score: int = 50,
) -> PortfolioProposal:
    """Allocate only to candidates that pass the independent validation gate.

    This function creates a paper proposal only. It has no broker integration and
    cannot place orders. Cash is retained if the universe has too few qualified
    candidates, which is intentional risk control rather than a missing feature.
    """

    if initial_capital <= 0:
        raise ValueError("initial_capital 必须为正数")
    if max_positions <= 0:
        raise ValueError("max_positions 必须为正数")
    if not 0 < max_position_fraction <= 1:
        raise ValueError("max_position_fraction 必须在 (0, 1] 之间")

    selected: list[Candidate] = []
    excluded: list[str] = []
    for candidate in candidates:
        passed = validation_passes.get(candidate.symbol, False)
        if candidate.decision.action != Action.BUY:
            excluded.append(f"{candidate.symbol}：当前动作为 {candidate.decision.action.value}，不建仓。")
        elif candidate.score < min_score:
            excluded.append(f"{candidate.symbol}：评分 {candidate.score} 低于门槛 {min_score}。")
        elif not passed:
            excluded.append(f"{candidate.symbol}：未通过样本外基准验证。")
        elif fundamental_scores is not None and candidate.symbol not in fundamental_scores:
            excluded.append(f"{candidate.symbol}：缺少基本面数据，不建仓。")
        elif fundamental_scores is not None and fundamental_scores[candidate.symbol] < min_fundamental_score:
            excluded.append(f"{candidate.symbol}：基本面评分 {fundamental_scores[candidate.symbol]} 低于门槛 {min_fundamental_score}。")
        elif candidate.decision.stop_loss_price is None:
            excluded.append(f"{candidate.symbol}：缺少止损价，拒绝建仓。")
        else:
            selected.append(candidate)

    selected = selected[:max_positions]
    weight = min(max_position_fraction, 1 / max_positions)
    allocations = tuple(
        Allocation(
            symbol=candidate.symbol,
            score=candidate.score,
            weight=weight,
            capital=initial_capital * weight,
            reference_price=candidate.close,
            stop_loss_price=candidate.decision.stop_loss_price or 0.0,
        )
        for candidate in selected
    )
    allocated = sum(item.capital for item in allocations)
    return PortfolioProposal(initial_capital, allocations, initial_capital - allocated, tuple(excluded))
