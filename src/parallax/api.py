from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROOF_PATH = PROJECT_ROOT / "evidence" / "counterfactual-proof.json"
PROOF_PATHS = {
    "payment-retry": PROOF_PATH,
    "stock-race": PROJECT_ROOT / "evidence" / "stock-race-counterfactual-proof.json",
}

app = FastAPI(title="PARALLAX Evidence API", version="0.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["Accept"],
)


def load_proof(path: Path = PROOF_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    proof = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "experiment_id",
        "verdict",
        "control",
        "counterfactual",
        "sources",
    }
    missing = sorted(required.difference(proof))
    if missing:
        raise ValueError(f"Proof is missing required fields: {', '.join(missing)}")
    proof["evidence_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return proof


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/proof")
def get_proof() -> dict[str, Any]:
    try:
        return load_proof()
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/proofs")
def get_proofs() -> dict[str, list[dict[str, Any]]]:
    proofs: list[dict[str, Any]] = []
    for proof_id, path in PROOF_PATHS.items():
        try:
            proof = load_proof(path)
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            continue
        proofs.append({"id": proof_id, "proof": proof})
    if not proofs:
        raise HTTPException(status_code=503, detail="No valid proof evidence is available")
    return {"proofs": proofs}
