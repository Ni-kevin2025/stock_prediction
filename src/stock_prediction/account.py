"""Local-only account inputs for manual order planning.

No broker credentials, account identifiers, or trading APIs are used here.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Holding:
    symbol: str
    shares: int
    average_cost: float

    def __post_init__(self) -> None:
        if self.shares <= 0 or self.shares % 100:
            raise ValueError("A 股持仓数量必须为正且为 100 股整数倍。")
        if self.average_cost <= 0:
            raise ValueError("持仓成本必须为正数。")


@dataclass(frozen=True)
class TradingProfile:
    available_cash: float
    risk_per_trade: float = 0.01
    max_position_fraction: float = 0.20
    holdings: tuple[Holding, ...] = ()
    watchlist: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.available_cash < 0:
            raise ValueError("可用现金不能为负数。")
        if not 0 < self.risk_per_trade <= 0.03:
            raise ValueError("单笔风险必须在 (0, 3%] 之间。")
        if not 0 < self.max_position_fraction <= 0.30:
            raise ValueError("单只股票上限必须在 (0, 30%] 之间。")
        if any(not symbol.isdigit() or len(symbol) != 6 or not symbol.startswith(("0", "3", "6", "9")) for symbol in self.watchlist):
            raise ValueError("自选股票必须是六码 A 股代码。")


def load_profile(path: Path) -> TradingProfile:
    """Load a user-owned local profile; absent files return a safe empty profile."""

    if not path.exists():
        return TradingProfile(available_cash=0.0)
    payload = json.loads(path.read_text(encoding="utf-8"))
    holdings = tuple(Holding(**item) for item in payload.get("holdings", []))
    return TradingProfile(
        available_cash=float(payload.get("available_cash", 0.0)),
        risk_per_trade=float(payload.get("risk_per_trade", 0.01)),
        max_position_fraction=float(payload.get("max_position_fraction", 0.20)),
        holdings=holdings,
        watchlist=tuple(str(symbol) for symbol in payload.get("watchlist", [])),
    )


def save_profile(path: Path, profile: TradingProfile) -> None:
    """Write profile data locally; callers should use a Git-ignored data path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(profile)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_watchlist(existing: tuple[str, ...] | list[str], pasted: str) -> tuple[str, ...]:
    """Merge pasted comma/space/newline-delimited A-share codes without duplicates."""

    codes: list[str] = []
    for value in [*existing, *re.split(r"[,\s]+", pasted)]:
        code = str(value).strip()
        if code.isdigit() and len(code) == 6 and code.startswith(("0", "3", "6", "9")) and code not in codes:
            codes.append(code)
    return tuple(codes)
