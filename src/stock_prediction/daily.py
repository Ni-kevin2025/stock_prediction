"""Aggregate the specialist agents into one daily research brief."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from stock_prediction.fundamentals import FundamentalSnapshot
from stock_prediction.portfolio import PortfolioProposal, propose_portfolio
from stock_prediction.screening import Candidate, rank_candidates
from stock_prediction.validation import ValidationResult, validate_out_of_sample


@dataclass(frozen=True)
class DailyBrief:
    candidates: tuple[Candidate, ...]
    validations: Mapping[str, ValidationResult | None]
    fundamentals: Mapping[str, FundamentalSnapshot | None]
    portfolio: PortfolioProposal
    issues: Mapping[str, str]


def build_daily_brief(
    histories: Mapping[str, pd.DataFrame],
    fundamentals: Mapping[str, FundamentalSnapshot | None],
    issues: Mapping[str, str] | None = None,
    initial_capital: float = 100_000.0,
) -> DailyBrief:
    """Combine already-fetched data; network retrieval remains outside the decision logic."""

    candidates = rank_candidates(histories)
    validations: dict[str, ValidationResult | None] = {}
    validation_passes: dict[str, bool] = {}
    for candidate in candidates:
        try:
            validation = validate_out_of_sample(histories[candidate.symbol])
        except ValueError:
            validation = None
        validations[candidate.symbol] = validation
        validation_passes[candidate.symbol] = validation.passed_benchmark if validation else False
    fundamental_scores = {
        symbol: snapshot.score for symbol, snapshot in fundamentals.items() if snapshot is not None
    }
    portfolio = propose_portfolio(
        candidates,
        validation_passes,
        fundamental_scores=fundamental_scores,
        initial_capital=initial_capital,
    )
    return DailyBrief(tuple(candidates), validations, fundamentals, portfolio, issues or {})
