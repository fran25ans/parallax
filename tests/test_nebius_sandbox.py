from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parallax.nebius_sandbox import (
    run_live_sandbox_smoke,
    sandbox_smoke_plan,
    stock_race_sandbox_plan,
    ticketshop_sandbox_plan,
)


class NebiusSandboxSafetyTest(unittest.TestCase):
    def test_plan_is_local_and_bounded(self) -> None:
        plan = sandbox_smoke_plan()
        self.assertEqual(len(plan), 6)
        self.assertIn("same parent checkpoint UUID", " ".join(plan))

    def test_live_run_fails_closed_without_explicit_spend_switch(self) -> None:
        with patch.dict(os.environ, {"PARALLAX_ALLOW_NEBIUS_SPEND": ""}):
            with self.assertRaisesRegex(RuntimeError, "Live Nebius execution is disabled"):
                run_live_sandbox_smoke(Path("unused.json"))

    def test_ticketshop_plan_is_bounded_to_three_operations(self) -> None:
        plan = ticketshop_sandbox_plan()
        self.assertEqual(len(plan), 6)
        self.assertIn("one persistent checkpoint", " ".join(plan))
        self.assertIn("disposable control branch", " ".join(plan))
        self.assertIn("Nemotron-selected capability", " ".join(plan))

    def test_stock_race_plan_is_bounded_to_three_operations(self) -> None:
        plan = stock_race_sandbox_plan()
        self.assertEqual(len(plan), 6)
        self.assertIn("one persistent checkpoint", " ".join(plan))
        self.assertIn("STOCK-001", " ".join(plan))

    def test_stock_race_fixture_proves_only_the_interleaved_branch(self) -> None:
        fixture = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "ticketshop"
            / "stock_race_experiment.py"
        )
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "checkpoint.sqlite3"
            subprocess.run(
                [sys.executable, str(fixture), "prepare", str(checkpoint)],
                check=True,
                capture_output=True,
                text=True,
            )
            control_db = Path(directory) / "control.sqlite3"
            race_db = Path(directory) / "race.sqlite3"
            control_db.write_bytes(checkpoint.read_bytes())
            race_db.write_bytes(checkpoint.read_bytes())
            control = json.loads(
                subprocess.run(
                    [sys.executable, str(fixture), "control", str(control_db)],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout
            )
            race = json.loads(
                subprocess.run(
                    [sys.executable, str(fixture), "race", str(race_db)],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout
            )

        self.assertEqual((control["sold_count"], control["invariant"]), (1, "PASS"))
        self.assertEqual((race["sold_count"], race["invariant"]), (2, "FAIL"))
        self.assertEqual(race["available_stock"], -1)


if __name__ == "__main__":
    unittest.main()
