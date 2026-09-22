from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RegressionRun:
    source: str
    output: str
    exit_code: int
    reproduced: bool


def compile_payment_regression() -> str:
    return '''from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from parallax.models import Event, InterventionType
from parallax.ticketshop import ResponseLost, TicketShop, create_checkpoint


class LostCheckoutResponseRegression(unittest.TestCase):
    def test_retry_after_lost_response_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = Path(temporary_directory) / "ticketshop.sqlite3"
            create_checkpoint(database)
            shop = TicketShop(database)
            events: list[Event] = []

            try:
                shop.checkout(
                    "cart-001",
                    events,
                    intervention=InterventionType.DROP_RESPONSE_AFTER_COMMIT,
                )
            except ResponseLost:
                shop.checkout("cart-001", events)

            state = shop.snapshot("cart-001")
            self.assertEqual(state["payment_count"], 1)


if __name__ == "__main__":
    unittest.main()
'''


def run_generated_regression(source: str, workspace: Path) -> RegressionRun:
    regression_directory = workspace / "regression"
    regression_directory.mkdir(parents=True, exist_ok=True)
    test_path = regression_directory / "test_px_payment_idempotency.py"
    test_path.write_text(source, encoding="utf-8")

    environment = os.environ.copy()
    source_root = Path(__file__).resolve().parents[1]
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{source_root}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else str(source_root)
    )
    completed = subprocess.run(
        [sys.executable, str(test_path)],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
        timeout=20,
    )
    output = completed.stdout + completed.stderr
    reproduced = completed.returncode != 0 and "2 != 1" in output
    return RegressionRun(
        source=source,
        output=output,
        exit_code=completed.returncode,
        reproduced=reproduced,
    )
