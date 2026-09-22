from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parallax.nemotron import parse_experiment_plan, stock_experiment_designer_prompt


class NemotronPlanValidationTest(unittest.TestCase):
    def test_valid_plan_is_accepted(self) -> None:
        plan = parse_experiment_plan(
            """{
              "branch_point": "after_payment_commit",
              "intervention": {"type": "drop_response_after_commit"},
              "hypothesis": "A retry may duplicate the payment.",
              "target_invariant": "PAY-001",
              "reason": "The commit precedes acknowledgement."
            }""",
            model="test-model",
            usage={"total_tokens": 100},
        )
        self.assertEqual(plan.intervention["type"], "drop_response_after_commit")

    def test_unknown_intervention_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the allowlist"):
            parse_experiment_plan(
                """{
                  "branch_point": "before_commit",
                  "intervention": {"type": "delete_database"},
                  "hypothesis": "Data disappears.",
                  "target_invariant": "PAY-001",
                  "reason": "Destructive action."
                }""",
                model="test-model",
                usage={},
            )

    def test_extra_schema_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "schema"):
            parse_experiment_plan(
                """{
                  "branch_point": "after_commit",
                  "intervention": {"type": "duplicate_request"},
                  "hypothesis": "Duplicate payment.",
                  "target_invariant": "PAY-001",
                  "reason": "No idempotency.",
                  "execute": true
                }""",
                model="test-model",
                usage={},
            )

    def test_stock_race_plan_is_accepted_for_stock_invariant(self) -> None:
        plan = parse_experiment_plan(
            """{
              "branch_point": "after_both_buyers_read_stock",
              "intervention": {"type": "interleave_two_buyers_after_stock_read"},
              "hypothesis": "Both buyers may commit the final ticket.",
              "target_invariant": "STOCK-001",
              "reason": "The check and write are not atomic."
            }""",
            model="test-model",
            usage={"total_tokens": 90},
            expected_invariant="STOCK-001",
        )
        self.assertEqual(plan.target_invariant, "STOCK-001")
        self.assertIn("STOCK-001", stock_experiment_designer_prompt())

    def test_stock_plan_cannot_be_parsed_as_payment_plan(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown invariant"):
            parse_experiment_plan(
                """{
                  "branch_point": "after_read",
                  "intervention": {"type": "interleave_two_buyers_after_stock_read"},
                  "hypothesis": "Oversell.",
                  "target_invariant": "STOCK-001",
                  "reason": "Race."
                }""",
                model="test-model",
                usage={},
            )


if __name__ == "__main__":
    unittest.main()
