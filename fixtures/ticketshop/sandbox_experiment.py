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


def read_cart(database: Path, actor: str, events: list[str]) -> int:
    with sqlite3.connect(database) as connection:
        amount = connection.execute(
            "SELECT amount_cents FROM carts WHERE id = 'cart-001'"
        ).fetchone()[0]
    events.append(f"{actor} READ cart")
    return amount


def commit_payment(database: Path, actor: str, amount: int, events: list[str]) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO payments (cart_id, amount_cents) VALUES (?, ?)",
            ("cart-001", amount),
        )
        connection.execute(
            "INSERT OR IGNORE INTO tickets (cart_id) VALUES ('cart-001')"
        )
        connection.commit()
    events.append(f"{actor} COMMIT payment")


def checkout(database: Path, actor: str, events: list[str]) -> None:
    events.append(f"{actor} POST /checkout")
    commit_payment(database, actor, read_cart(database, actor, events), events)


def execute(database: Path, branch: str) -> None:
    branch = {"response-lost": "drop_response_after_commit"}.get(branch, branch)
    events: list[str] = []
    if branch == "interleave_two_actors_after_read":
        events.extend(["actor-a POST /checkout", "actor-b POST /checkout"])
        amount_a = read_cart(database, "actor-a", events)
        amount_b = read_cart(database, "actor-b", events)
        events.append("INTERLEAVE actors after cart read")
        commit_payment(database, "actor-a", amount_a, events)
        commit_payment(database, "actor-b", amount_b, events)
    else:
        checkout(database, "actor-a", events)
    if branch == "drop_response_after_commit":
        events.extend(["DROP response", "CLIENT retry"])
        checkout(database, "actor-a", events)
    elif branch == "duplicate_request":
        events.append("DUPLICATE request")
        checkout(database, "actor-a", events)
    elif branch == "delay_response":
        events.append("DELAY response")
    elif branch == "reorder_independent_events":
        events.append("REORDER independent telemetry event")
    elif branch in {"control", "no_intervention", "interleave_two_actors_after_read"}:
        events.append("HTTP 200 delivered")
    else:
        raise ValueError(f"unknown branch: {branch}")

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
        raise SystemExit("usage: sandbox_experiment.py ACTION DB")
    action = sys.argv[1]
    database = Path(sys.argv[2])
    if action == "prepare":
        prepare(database)
        print(json.dumps({"checkpoint": "ready", "database": str(database)}))
        return 0
    if action in {
        "control",
        "response-lost",
        "delay_response",
        "drop_response_after_commit",
        "duplicate_request",
        "interleave_two_actors_after_read",
        "reorder_independent_events",
        "no_intervention",
    }:
        execute(database, action)
        return 0
    raise SystemExit(f"unknown action: {action}")


if __name__ == "__main__":
    raise SystemExit(main())
