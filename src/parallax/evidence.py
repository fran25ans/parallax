from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import CounterfactualProof
from .regression import RegressionRun


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(65536), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()}"


def write_evidence_bundle(
    proof: CounterfactualProof, output: Path, regression: RegressionRun
) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    payloads = {
        "manifest.json": proof.to_dict(),
        "control-events.json": [asdict(event) for event in proof.control.events],
        "counterfactual-events.json": [asdict(event) for event in proof.counterfactual.events],
        "state-diff.json": {
            "control": proof.control.state,
            "counterfactual": proof.counterfactual.state,
        },
        "invariant-result.json": {
            "id": proof.control.invariant_id,
            "control": proof.control.invariant_status,
            "counterfactual": proof.counterfactual.invariant_status,
            "proven": proof.proven,
        },
        "generated-test.py": regression.source,
        "generated-test-output.txt": regression.output,
    }

    for filename, payload in payloads.items():
        if isinstance(payload, str):
            rendered = payload
        else:
            rendered = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
        (output / filename).write_text(rendered, encoding="utf-8")

    checksum_lines = []
    for filename in sorted(payloads):
        checksum_lines.append(f"{sha256_file(output / filename)}  {filename}")
    (output / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return output


def verify_evidence_bundle(output: Path) -> tuple[bool, list[str]]:
    checksum_file = output / "SHA256SUMS"
    if not checksum_file.is_file():
        return False, ["SHA256SUMS is missing"]

    failures: list[str] = []
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        expected, separator, filename = line.partition("  ")
        artifact = output / filename
        if not separator or not filename:
            failures.append(f"Malformed checksum line: {line}")
        elif not artifact.is_file():
            failures.append(f"Missing artifact: {filename}")
        elif sha256_file(artifact) != expected:
            failures.append(f"Checksum mismatch: {filename}")
    return not failures, failures
