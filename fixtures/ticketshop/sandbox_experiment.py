from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


SCHEMA = """
CREATE TABLE carts (
    id TEXT PRIMARY KEY,
    amount_cents INTEGER NOT NULL
);
CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id TEXT NOT NULL,
    amount_cents INTEGER NOT NULL
);
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_id TEXT NOT NULL UNIQUE
);
"""


def prepare(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT INTO carts (id, amount_cents) VALUES (?, ?)",
            ("cart-001", 4900),
        )


def checkout(database: Path, events: list[str]) -> None:
    events.append("POST /checkout")
    with sqlite3.connect(database) as connection:
        amount = connection.execute(
            "SELECT amount_cents FROM carts WHERE id = 'cart-001'"
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO payments (cart_id, amount_cents) VALUES (?, ?)",
            ("cart-001", amount),
        )
        connection.execute(
            "INSERT OR IGNORE INTO tickets (cart_id) VALUES ('cart-001')"
        )
        connection.commit()
    events.append("COMMIT payment")


def execute(database: Path, branch: str) -> None:
    events: list[str] = []
    checkout(database, events)
    if branch == "response-lost":
        events.extend(["DROP response", "CLIENT retry"])
        checkout(database, events)
    else:
        events.append("HTTP 200 delivered")

    with sqlite3.connect(database) as connection:
        payment_count, total = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_cents), 0) FROM payments"
        ).fetchone()
        ticket_count = connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]

    result = {
        "branch": branch,
        "events": events,
        "payment_count": payment_count,
        "ticket_count": ticket_count,
        "total_charged_cents": total,
        "invariant": "PASS" if payment_count <= 1 else "FAIL",
    }
    print(json.dumps(result, sort_keys=True))


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: sandbox_experiment.py prepare|control|response-lost DB")
    action = sys.argv[1]
    database = Path(sys.argv[2])
    if action == "prepare":
        prepare(database)
        print(json.dumps({"checkpoint": "ready", "database": str(database)}))
        return 0
    if action in {"control", "response-lost"}:
        execute(database, action)
        return 0
    raise SystemExit(f"unknown action: {action}")


if __name__ == "__main__":
    raise SystemExit(main())
