from pathlib import Path

from stock_prediction.paper import PaperLedger
from stock_prediction.portfolio import Allocation, PortfolioProposal


def _proposal() -> PortfolioProposal:
    return PortfolioProposal(
        initial_capital=100_000,
        allocations=(Allocation("TEST", 90, 0.2, 20_000, 100.0, 92.0),),
        unallocated_cash=80_000,
        excluded=(),
    )


def test_paper_ledger_requires_manual_approval(tmp_path: Path) -> None:
    ledger = PaperLedger(tmp_path / "paper.sqlite")

    recorded = ledger.record_proposal(_proposal())
    approved = ledger.approve(recorded[0].id)

    assert recorded[0].status == "proposed"
    assert approved.status == "approved"
    assert approved.quantity == 200
