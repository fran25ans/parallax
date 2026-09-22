from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parallax.nemotron import (
    INTERVENTION_CAPABILITIES,
    experiment_designer_prompt,
    parse_experiment_plan,
)


def plan_payload(
    invariant: str = "PAY-001",
    selected: str = "drop_response_after_commit",
) -> dict[str, object]:
    alternatives = (
        ["interleave_two_actors_after_read", "reorder_independent_events"]
        if selected == "drop_response_after_commit"
        else ["duplicate_request", "no_intervention"]
    )
    return {
        "branch_point": "after a committed state change",
        "intervention": {"type": selected},
        "hypothesis": "The intervention may violate the target invariant.",
        "expected_observable": "The branch state differs in a declared counter.",
        "target_invariant": invariant,
        "reason": "The selected intervention directly stresses the state transition.",
        "ranked_candidates": [
            {"type": selected, "score": 0.94, "rationale": "Direct causal test."},
            {"type": alternatives[0], "score": 0.52, "rationale": "Secondary test."},
            {"type": alternatives[1], "score": 0.18, "rationale": "Weak control."},
        ],
    }


class NemotronPlanValidationTest(unittest.TestCase):
    def parse(self, payload: dict[str, object], invariant: str = "PAY-001"):
        return parse_experiment_plan(
            json.dumps(payload),
            model="test-model",
            usage={"total_tokens": 100},
            expected_invariant=invariant,
        )

    def test_valid_ranked_plan_is_accepted(self) -> None:
        plan = self.parse(plan_payload())
        self.assertEqual(plan.intervention["type"], "drop_response_after_commit")
        self.assertEqual(len(plan.ranked_candidates), 3)

    def test_generic_prompt_offers_same_capabilities_to_both_scenarios(self) -> None:
        payment = experiment_designer_prompt("payment-retry")
        stock = experiment_designer_prompt("stock-race")
        for capability in INTERVENTION_CAPABILITIES:
            self.assertIn(capability, payment)
            self.assertIn(capability, stock)
        self.assertIn("PAY-001", payment)
        self.assertIn("STOCK-001", stock)

    def test_unknown_intervention_is_rejected(self) -> None:
        payload = plan_payload()
        payload["intervention"] = {"type": "delete_database"}
        with self.assertRaisesRegex(ValueError, "outside the allowlist"):
            self.parse(payload)

    def test_extra_schema_fields_are_rejected(self) -> None:
        payload = plan_payload()
        payload["execute"] = True
        with self.assertRaisesRegex(ValueError, "schema"):
            self.parse(payload)

    def test_stock_race_plan_is_accepted_for_stock_invariant(self) -> None:
        payload = plan_payload(
            invariant="STOCK-001",
            selected="interleave_two_actors_after_read",
        )
        plan = self.parse(payload, invariant="STOCK-001")
        self.assertEqual(plan.target_invariant, "STOCK-001")

    def test_stock_plan_cannot_be_parsed_as_payment_plan(self) -> None:
        payload = plan_payload(
            invariant="STOCK-001",
            selected="interleave_two_actors_after_read",
        )
        with self.assertRaisesRegex(ValueError, "unknown invariant"):
            self.parse(payload)

    def test_selected_candidate_must_rank_first(self) -> None:
        payload = plan_payload()
        payload["ranked_candidates"][0]["type"] = "duplicate_request"  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "top-ranked"):
            self.parse(payload)

    def test_scores_must_be_descending(self) -> None:
        payload = plan_payload()
        payload["ranked_candidates"][1]["score"] = 0.99  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "descend"):
            self.parse(payload)

    def test_duplicate_ranked_candidates_are_rejected(self) -> None:
        payload = plan_payload()
        payload["ranked_candidates"][1]["type"] = payload["ranked_candidates"][0]["type"]  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.parse(payload)


if __name__ == "__main__":
    unittest.main()
