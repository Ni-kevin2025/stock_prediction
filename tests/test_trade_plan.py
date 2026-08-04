import numpy as np
import pandas as pd

from stock_prediction.account import Holding, TradingProfile
from stock_prediction.daily import build_daily_brief
from stock_prediction.fundamentals import FundamentalSnapshot
from stock_prediction.portfolio import Allocation, PortfolioProposal
from stock_prediction.screening import Candidate
from stock_prediction.strategy import Action, Decision
from stock_prediction.trade_plan import build_trade_plan


def _history() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=220, freq="B")
    prices = 20 + np.arange(220) * 0.04 + np.sin(np.arange(220) / 3)
    return pd.DataFrame({"open": prices, "high": prices + 0.5, "low": prices - 0.5, "close": prices, "volume": 1_000_000}, index=dates)


def test_trade_plan_keeps_cash_when_no_candidate_is_qualified() -> None:
    brief = build_daily_brief({"TEST": _history()}, {})
    plan = build_trade_plan(brief, TradingProfile(available_cash=100_000))

    assert plan.planned_orders[-1].action == "CASH"


def test_existing_holding_gets_stop_loss_review() -> None:
    snapshot = FundamentalSnapshot("TEST", pd.Timestamp("2025-12-31"), 20, 10, 10, 30, 2, 100, (), ())
    brief = build_daily_brief({"TEST": _history()}, {"TEST": snapshot})
    plan = build_trade_plan(brief, TradingProfile(available_cash=100_000, holdings=(Holding("TEST", 100, 22.0),)))

    assert plan.planned_orders[0].symbol == "TEST"
    assert plan.planned_orders[0].action in {"HOLD", "SELL"}
    assert plan.planned_orders[0].stop_loss == 20.24


def test_buy_plan_rounds_risk_limited_quantity_to_a_lot() -> None:
    decision = Decision("TEST", pd.Timestamp("2026-01-01"), Action.BUY, 0.2, 92.0, "medium", (), ())
    candidate = Candidate("TEST", 90, decision, 100.0, 60.0, ())
    brief = type("Brief", (), {
        "candidates": (candidate,),
        "portfolio": PortfolioProposal(100_000, (Allocation("TEST", 90, 0.2, 20_000, 100.0, 92.0),), 80_000, ()),
    })()

    plan = build_trade_plan(brief, TradingProfile(available_cash=100_000, risk_per_trade=0.01))

    assert plan.planned_orders[0].action == "BUY"
    assert plan.planned_orders[0].quantity == 100
