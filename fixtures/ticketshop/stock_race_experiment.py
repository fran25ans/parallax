from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


SCHEMA = """
CREATE TABLE inventory (
    sku TEXT PRIMARY KEY,
    available INTEGER NOT NULL
);
CREATE TABLE sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL,
    buyer TEXT NOT NULL
);
"""


def prepare(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT INTO inventory (sku, available) VALUES (?, ?)",
            ("ticket-last", 1),
        )


def read_stock(connection: sqlite3.Connection, buyer: str, events: list[str]) -> int:
    available = connection.execute(
        "SELECT available FROM inventory WHERE sku = 'ticket-last'"
    ).fetchone()[0]
    events.append(f"{buyer} READ stock={available}")
    return available


def commit_sale(connection: sqlite3.Connection, buyer: str, events: list[str]) -> None:
    connection.execute(
        "INSERT INTO sales (sku, buyer) VALUES ('ticket-last', ?)",
        (buyer,),
    )
    connection.execute(
        "UPDATE inventory SET available = available - 1 WHERE sku = 'ticket-last'"
    )
    connection.commit()
    events.append(f"{buyer} COMMIT sale")


def execute(database: Path, branch: str) -> None:
    events: list[str] = []
    with sqlite3.connect(database) as connection:
        if branch == "control":
            if read_stock(connection, "buyer-a", events) > 0:
                commit_sale(connection, "buyer-a", events)
        elif branch == "race":
            stock_a = read_stock(connection, "buyer-a", events)
            stock_b = read_stock(connection, "buyer-b", events)
            events.append("INTERLEAVE buyers after stock read")
            if stock_a > 0:
                commit_sale(connection, "buyer-a", events)
            if stock_b > 0:
                commit_sale(connection, "buyer-b", events)
        else:
            raise ValueError(f"unknown branch: {branch}")

        sold_count = connection.execute(
            "SELECT COUNT(*) FROM sales WHERE sku = 'ticket-last'"
        ).fetchone()[0]
        available = connection.execute(
            "SELECT available FROM inventory WHERE sku = 'ticket-last'"
        ).fetchone()[0]

    invariant = "PASS" if sold_count <= 1 and available >= 0 else "FAIL"
    print(
        json.dumps(
            {
                "branch": branch,
                "events": events,
                "sold_count": sold_count,
                "available_stock": available,
                "invariant": invariant,
            },
            sort_keys=True,
        )
    )


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: stock_race_experiment.py prepare|control|race DB")
    action = sys.argv[1]
    database = Path(sys.argv[2])
    if action == "prepare":
        prepare(database)
        print(json.dumps({"checkpoint": "ready", "database": str(database)}))
        return 0
    if action in {"control", "race"}:
        execute(database, action)
        return 0
    raise SystemExit(f"unknown action: {action}")


if __name__ == "__main__":
    raise SystemExit(main())
