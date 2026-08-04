import pandas as pd

from stock_prediction.portfolio import propose_portfolio
from stock_prediction.screening import Candidate
from stock_prediction.strategy import Action, Decision


def _candidate(symbol: str, score: int, action: Action = Action.BUY) -> Candidate:
    decision = Decision(
        symbol=symbol,
        as_of=pd.Timestamp("2026-01-01"),
        action=action,
        target_position_fraction=0.2 if action == Action.BUY else 0.0,
        stop_loss_price=10.0 if action == Action.BUY else None,
        confidence="medium",
        reasons=(),
        risk_notes=(),
    )
    return Candidate(symbol, score, decision, 12.0, 60.0, ())


def test_portfolio_only_allocates_to_validated_buy_candidates() -> None:
    candidates = [_candidate("PASS", 90), _candidate("FAIL", 90), _candidate("WAIT", 90, Action.WAIT)]

    proposal = propose_portfolio(candidates, {"PASS": True, "FAIL": False, "WAIT": True})

    assert [item.symbol for item in proposal.allocations] == ["PASS"]
    assert proposal.allocations[0].capital == 20_000
    assert proposal.unallocated_cash == 80_000
    assert len(proposal.excluded) == 2


def test_portfolio_caps_number_of_positions() -> None:
    candidates = [_candidate(f"S{i}", 90) for i in range(6)]

    proposal = propose_portfolio(candidates, {candidate.symbol: True for candidate in candidates})

    assert len(proposal.allocations) == 5
    assert proposal.unallocated_cash == 0


def test_portfolio_requires_fundamentals_when_scores_are_supplied() -> None:
    proposal = propose_portfolio([_candidate("PASS", 90)], {"PASS": True}, fundamental_scores={})

    assert not proposal.allocations
    assert "缺少基本面数据" in proposal.excluded[0]
