"""Local-only paper-trading proposal ledger with mandatory manual approval."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from stock_prediction.portfolio import PortfolioProposal


@dataclass(frozen=True)
class PaperOrder:
    id: int
    created_at: str
    symbol: str
    side: str
    quantity: float
    reference_price: float
    stop_loss_price: float
    status: str


class PaperLedger:
    """Persist *simulated* order proposals. No method connects to a broker."""

    def __init__(self, database: Path) -> None:
        self.database = database
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
                    quantity REAL NOT NULL CHECK (quantity > 0),
                    reference_price REAL NOT NULL CHECK (reference_price > 0),
                    stop_loss_price REAL NOT NULL CHECK (stop_loss_price > 0),
                    status TEXT NOT NULL CHECK (status IN ('proposed', 'approved', 'rejected'))
                )
                """
            )

    def record_proposal(self, proposal: PortfolioProposal) -> list[PaperOrder]:
        """Store buy proposals as `proposed`; this never executes a trade."""

        created_at = datetime.now(UTC).isoformat()
        recorded: list[PaperOrder] = []
        with self._connect() as connection:
            for allocation in proposal.allocations:
                quantity = allocation.capital / allocation.reference_price
                cursor = connection.execute(
                    """
                    INSERT INTO paper_orders
                        (created_at, symbol, side, quantity, reference_price, stop_loss_price, status)
                    VALUES (?, ?, 'buy', ?, ?, ?, 'proposed')
                    """,
                    (created_at, allocation.symbol, quantity, allocation.reference_price, allocation.stop_loss_price),
                )
                recorded.append(PaperOrder(cursor.lastrowid, created_at, allocation.symbol, "buy", quantity, allocation.reference_price, allocation.stop_loss_price, "proposed"))
        return recorded

    def list_orders(self) -> list[PaperOrder]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, created_at, symbol, side, quantity, reference_price, stop_loss_price, status FROM paper_orders ORDER BY id"
            ).fetchall()
        return [PaperOrder(*row) for row in rows]

    def approve(self, order_id: int) -> PaperOrder:
        """Mark a paper order approved after human review; still no execution."""

        with self._connect() as connection:
            changed = connection.execute(
                "UPDATE paper_orders SET status = 'approved' WHERE id = ? AND status = 'proposed'", (order_id,)
            ).rowcount
        if changed != 1:
            raise ValueError("订单不存在或当前不是 proposed 状态，无法批准。")
        return next(order for order in self.list_orders() if order.id == order_id)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)
