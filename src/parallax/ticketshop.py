from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import Event, InterventionType


class ResponseLost(RuntimeError):
    """The server committed the operation, but its response did not arrive."""


SCHEMA = """
CREATE TABLE carts (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    amount_cents INTEGER NOT NULL
);
CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    FOREIGN KEY(cart_id) REFERENCES carts(id)
);
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id TEXT NOT NULL UNIQUE,
    customer_id TEXT NOT NULL,
    FOREIGN KEY(cart_id) REFERENCES carts(id)
);
"""


def create_checkpoint(database: Path) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT INTO carts (id, customer_id, amount_cents) VALUES (?, ?, ?)",
            ("cart-001", "customer-001", 4900),
        )


class TicketShop:
    def __init__(self, database: Path) -> None:
        self.database = database

    def checkout(
        self,
        cart_id: str,
        events: list[Event],
        intervention: InterventionType = InterventionType.NONE,
    ) -> dict[str, int | str]:
        self._event(events, "checkout.requested", cart_id=cart_id)
        with sqlite3.connect(self.database) as connection:
            cart = connection.execute(
                "SELECT customer_id, amount_cents FROM carts WHERE id = ?", (cart_id,)
            ).fetchone()
            if cart is None:
                raise ValueError(f"Unknown cart: {cart_id}")

            customer_id, amount_cents = cart
            payment = connection.execute(
                "INSERT INTO payments (cart_id, amount_cents) VALUES (?, ?)",
                (cart_id, amount_cents),
            )
            connection.execute(
                "INSERT OR IGNORE INTO tickets (cart_id, customer_id) VALUES (?, ?)",
                (cart_id, customer_id),
            )
            connection.commit()
            self._event(
                events,
                "payment.committed",
                cart_id=cart_id,
                payment_id=payment.lastrowid,
                amount_cents=amount_cents,
            )

        if intervention == InterventionType.DROP_RESPONSE_AFTER_COMMIT:
            self._event(events, "transport.response_lost", cart_id=cart_id)
            raise ResponseLost("Response lost after database commit")

        self._event(events, "checkout.response_delivered", cart_id=cart_id, status=200)
        return {"status": "paid", "payment_id": int(payment.lastrowid)}

    def snapshot(self, cart_id: str) -> dict[str, int | str]:
        with sqlite3.connect(self.database) as connection:
            payment_count, total_charged = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount_cents), 0) FROM payments WHERE cart_id = ?",
                (cart_id,),
            ).fetchone()
            ticket_count = connection.execute(
                "SELECT COUNT(*) FROM tickets WHERE cart_id = ?", (cart_id,)
            ).fetchone()[0]
        return {
            "cart_id": cart_id,
            "payment_count": payment_count,
            "ticket_count": ticket_count,
            "total_charged_cents": total_charged,
        }

    @staticmethod
    def _event(events: list[Event], event_type: str, **detail: object) -> None:
        events.append(Event(sequence=len(events) + 1, type=event_type, detail=detail))

