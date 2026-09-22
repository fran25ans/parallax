from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


PROOF_FILES = {
    "payment-retry": "counterfactual-proof.json",
    "stock-race": "stock-race-counterfactual-proof.json",
}

SOURCE_FILES = {
    "payment-retry": {
        "experiment_plan": "nemotron-experiment-plan-v0.3.json",
        "sandbox_execution": "nebius-ticketshop-proof-v0.3.json",
    },
    "stock-race": {
        "experiment_plan": "nemotron-stock-race-plan-v0.3.json",
        "sandbox_execution": "nebius-stock-race-proof-v0.3.json",
    },
}


def build_static_catalog(evidence_directory: Path) -> dict[str, list[dict[str, Any]]]:
    proofs: list[dict[str, Any]] = []
    for proof_id, filename in PROOF_FILES.items():
        path = evidence_directory / filename
        raw = path.read_bytes()
        proof = json.loads(raw)
        proof["evidence_sha256"] = hashlib.sha256(raw).hexdigest()
        artifacts = {
            "assembled_proof": {
                "path": f"evidence/{filename}",
                "sha256": proof["evidence_sha256"],
            }
        }
        for source_name, source_filename in SOURCE_FILES[proof_id].items():
            source_path = evidence_directory / source_filename
            artifacts[source_name] = {
                "path": f"evidence/{source_filename}",
                "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            }
        proofs.append({"id": proof_id, "proof": proof, "artifacts": artifacts})
    return {"proofs": proofs}


def write_static_catalog(evidence_directory: Path, output: Path) -> None:
    catalog = build_static_catalog(evidence_directory)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    public_evidence = output.parent / "evidence"
    public_evidence.mkdir(parents=True, exist_ok=True)
    filenames = set(PROOF_FILES.values())
    filenames.update(
        filename for sources in SOURCE_FILES.values() for filename in sources.values()
    )
    for filename in filenames:
        shutil.copyfile(evidence_directory / filename, public_evidence / filename)
