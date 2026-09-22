from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parallax.evidence import sha256_file, verify_evidence_bundle
from parallax.experiment import CounterfactualExperiment
from parallax.models import InterventionType, InvariantStatus


class CounterfactualExperimentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        self.outcome = CounterfactualExperiment(self.workspace).run()
        self.proof = self.outcome.proof

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_control_timeline_passes(self) -> None:
        self.assertEqual(self.proof.control.state["payment_count"], 1)
        self.assertEqual(self.proof.control.state["ticket_count"], 1)
        self.assertEqual(self.proof.control.invariant_status, InvariantStatus.PASS)

    def test_drop_after_commit_duplicates_payment(self) -> None:
        self.assertEqual(self.proof.counterfactual.state["payment_count"], 2)
        self.assertEqual(self.proof.counterfactual.state["ticket_count"], 1)
        self.assertEqual(
            self.proof.counterfactual.invariant_status, InvariantStatus.FAIL
        )

    def test_branches_start_from_identical_checkpoint(self) -> None:
        self.assertTrue(self.proof.same_initial_state)
        self.assertEqual(
            self.proof.control.checkpoint_hash,
            self.proof.counterfactual.checkpoint_hash,
        )

    def test_only_one_intervention_changes(self) -> None:
        self.assertTrue(self.proof.single_intervention)
        self.assertEqual(self.proof.control.intervention.type, InterventionType.NONE)
        self.assertEqual(
            self.proof.counterfactual.intervention.type,
            InterventionType.DROP_RESPONSE_AFTER_COMMIT,
        )

    def test_counterexample_is_proven_by_deterministic_checks(self) -> None:
        self.assertTrue(self.proof.proven)
        self.assertEqual(self.proof.control.invariant_id, "PAY-001")
        self.assertTrue(self.proof.regression_reproduced)
        self.assertNotEqual(self.proof.regression_exit_code, 0)

    def test_evidence_bundle_is_complete_and_checksummed(self) -> None:
        expected = {
            "manifest.json",
            "control-events.json",
            "counterfactual-events.json",
            "state-diff.json",
            "invariant-result.json",
            "generated-test.py",
            "generated-test-output.txt",
            "SHA256SUMS",
        }
        self.assertEqual(
            {path.name for path in self.outcome.evidence_directory.iterdir()}, expected
        )
        manifest = json.loads(
            (self.outcome.evidence_directory / "manifest.json").read_text()
        )
        self.assertTrue(manifest["proven"])
        checksums = (self.outcome.evidence_directory / "SHA256SUMS").read_text()
        self.assertIn(sha256_file(self.outcome.evidence_directory / "manifest.json"), checksums)
        valid, failures = verify_evidence_bundle(self.outcome.evidence_directory)
        self.assertTrue(valid, failures)

    def test_tampered_evidence_is_rejected(self) -> None:
        manifest = self.outcome.evidence_directory / "manifest.json"
        manifest.write_text(manifest.read_text() + "tampered", encoding="utf-8")
        valid, failures = verify_evidence_bundle(self.outcome.evidence_directory)
        self.assertFalse(valid)
        self.assertIn("Checksum mismatch: manifest.json", failures)


if __name__ == "__main__":
    unittest.main()
