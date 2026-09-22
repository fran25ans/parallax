from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parallax.proof import assemble_counterfactual_proof


class CounterfactualProofAssemblyTest(unittest.TestCase):
    def test_matching_plan_and_execution_are_proven(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            plan = root / "plan.json"
            execution = root / "execution.json"
            output = root / "proof.json"
            plan.write_text(
                json.dumps(
                    {
                        "intervention": {"type": "drop_response_after_commit"},
                        "model": "test-model",
                        "usage": {"total_tokens": 10},
                        "hypothesis": "Retry duplicates payment.",
                        "branch_point": "after_commit",
                        "target_invariant": "PAY-001",
                    }
                )
            )
            execution.write_text(
                json.dumps(
                    {
                        "single_intervention": "response_after_commit=LOST",
                        "same_checkpoint": True,
                        "proven": True,
                        "checkpoint_uuid": "checkpoint-test",
                        "control": {"invariant": "PASS", "payment_count": 1},
                        "counterfactual": {"invariant": "FAIL", "payment_count": 2},
                    }
                )
            )
            proof = assemble_counterfactual_proof(plan, execution, output)
            self.assertEqual(proof["verdict"], "PROVEN")
            self.assertTrue(proof["plan_matches_execution"])

    def test_mismatched_intervention_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            plan = root / "plan.json"
            execution = root / "execution.json"
            plan.write_text(
                json.dumps(
                    {
                        "intervention": {"type": "delay_response"},
                        "model": "test-model",
                        "usage": {},
                        "hypothesis": "Delay duplicates payment.",
                        "branch_point": "after_commit",
                        "target_invariant": "PAY-001",
                    }
                )
            )
            execution.write_text(
                json.dumps(
                    {
                        "single_intervention": "response_after_commit=LOST",
                        "same_checkpoint": True,
                        "proven": True,
                        "checkpoint_uuid": "checkpoint-test",
                        "control": {"invariant": "PASS", "payment_count": 1},
                        "counterfactual": {"invariant": "FAIL", "payment_count": 2},
                    }
                )
            )
            proof = assemble_counterfactual_proof(
                plan, execution, root / "proof.json"
            )
            self.assertEqual(proof["verdict"], "NOT_PROVEN")

    def test_plan_whose_selection_is_not_top_ranked_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            plan = root / "plan.json"
            execution = root / "execution.json"
            plan.write_text(
                json.dumps(
                    {
                        "intervention": {"type": "drop_response_after_commit"},
                        "ranked_candidates": [
                            {"type": "duplicate_request", "score": 0.9},
                            {"type": "drop_response_after_commit", "score": 0.8},
                            {"type": "delay_response", "score": 0.2},
                        ],
                        "model": "test-model",
                        "usage": {},
                        "hypothesis": "Retry duplicates payment.",
                        "branch_point": "after_commit",
                        "target_invariant": "PAY-001",
                    }
                )
            )
            execution.write_text(
                json.dumps(
                    {
                        "single_intervention": "capability=drop_response_after_commit",
                        "same_checkpoint": True,
                        "proven": True,
                        "checkpoint_uuid": "checkpoint-test",
                        "control": {"invariant": "PASS", "payment_count": 1},
                        "counterfactual": {"invariant": "FAIL", "payment_count": 2},
                    }
                )
            )
            proof = assemble_counterfactual_proof(
                plan, execution, root / "proof.json"
            )
            self.assertFalse(proof["planner_selection_valid"])
            self.assertEqual(proof["verdict"], "NOT_PROVEN")


if __name__ == "__main__":
    unittest.main()
