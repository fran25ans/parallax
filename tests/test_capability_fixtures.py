from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES = (
    "delay_response",
    "drop_response_after_commit",
    "duplicate_request",
    "interleave_two_actors_after_read",
    "reorder_independent_events",
    "no_intervention",
)


def fixture_result(fixture: Path, capability: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temporary:
        database = Path(temporary) / "state.sqlite3"
        subprocess.run(
            [sys.executable, str(fixture), "prepare", str(database)],
            check=True,
            capture_output=True,
            text=True,
        )
        completed = subprocess.run(
            [sys.executable, str(fixture), capability, str(database)],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)


class CapabilityFixtureTest(unittest.TestCase):
    def test_all_capabilities_execute_in_both_fixtures(self) -> None:
        fixtures = (
            ROOT / "fixtures" / "ticketshop" / "sandbox_experiment.py",
            ROOT / "fixtures" / "ticketshop" / "stock_race_experiment.py",
        )
        for fixture in fixtures:
            for capability in CAPABILITIES:
                with self.subTest(fixture=fixture.name, capability=capability):
                    result = fixture_result(fixture, capability)
                    self.assertIn(result["invariant"], {"PASS", "FAIL"})

    def test_selected_interleaving_breaks_both_invariants(self) -> None:
        payment = fixture_result(
            ROOT / "fixtures" / "ticketshop" / "sandbox_experiment.py",
            "interleave_two_actors_after_read",
        )
        stock = fixture_result(
            ROOT / "fixtures" / "ticketshop" / "stock_race_experiment.py",
            "interleave_two_actors_after_read",
        )
        self.assertEqual(payment["payment_count"], 2)
        self.assertEqual(payment["invariant"], "FAIL")
        self.assertEqual(stock["sold_count"], 2)
        self.assertEqual(stock["invariant"], "FAIL")


if __name__ == "__main__":
    unittest.main()
