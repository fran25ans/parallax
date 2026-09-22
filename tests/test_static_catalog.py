from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parallax.static_catalog import build_static_catalog, write_static_catalog


ROOT = Path(__file__).resolve().parents[1]


class StaticCatalogTest(unittest.TestCase):
    def test_catalog_contains_real_hashed_proofs(self) -> None:
        catalog = build_static_catalog(ROOT / "evidence")
        self.assertEqual(
            [entry["id"] for entry in catalog["proofs"]],
            ["payment-retry", "stock-race"],
        )
        for entry in catalog["proofs"]:
            self.assertEqual(entry["proof"]["verdict"], "PROVEN")
            self.assertEqual(len(entry["proof"]["evidence_sha256"]), 64)

    def test_written_catalog_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "proofs.json"
            write_static_catalog(ROOT / "evidence", output)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                build_static_catalog(ROOT / "evidence"),
            )


if __name__ == "__main__":
    unittest.main()
