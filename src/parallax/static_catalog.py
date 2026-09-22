from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROOF_FILES = {
    "payment-retry": "counterfactual-proof.json",
    "stock-race": "stock-race-counterfactual-proof.json",
}


def build_static_catalog(evidence_directory: Path) -> dict[str, list[dict[str, Any]]]:
    proofs: list[dict[str, Any]] = []
    for proof_id, filename in PROOF_FILES.items():
        path = evidence_directory / filename
        raw = path.read_bytes()
        proof = json.loads(raw)
        proof["evidence_sha256"] = hashlib.sha256(raw).hexdigest()
        proofs.append({"id": proof_id, "proof": proof})
    return {"proofs": proofs}


def write_static_catalog(evidence_directory: Path, output: Path) -> None:
    catalog = build_static_catalog(evidence_directory)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
