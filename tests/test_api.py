import json
import tempfile
import unittest
from pathlib import Path

from parallax.api import get_proofs, load_proof


class ApiTest(unittest.TestCase):
    def test_load_proof_adds_hash_without_changing_source(self) -> None:
        payload = {
            "experiment_id": "px_test",
            "verdict": "PROVEN",
            "control": {},
            "counterfactual": {},
            "sources": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_proof(path)

            self.assertEqual(loaded["experiment_id"], "px_test")
            self.assertEqual(len(loaded["evidence_sha256"]), 64)
            self.assertNotIn("evidence_sha256", json.loads(path.read_text()))

    def test_load_proof_rejects_incomplete_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_text('{"verdict": "PROVEN"}', encoding="utf-8")

            with self.assertRaises(ValueError):
                load_proof(path)

    def test_proof_catalog_exposes_both_verified_experiments(self) -> None:
        catalog = get_proofs()
        ids = {entry["id"] for entry in catalog["proofs"]}
        self.assertEqual(ids, {"payment-retry", "stock-race"})
        self.assertTrue(all(entry["proof"]["verdict"] == "PROVEN" for entry in catalog["proofs"]))


if __name__ == "__main__":
    unittest.main()
