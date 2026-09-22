from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


EXECUTED_INTERVENTIONS = {
    "response_after_commit=LOST": "drop_response_after_commit",
    "buyers_after_stock_read=INTERLEAVED": "interleave_two_buyers_after_stock_read",
}


def file_hash(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def assemble_counterfactual_proof(
    plan_path: Path, sandbox_proof_path: Path, output: Path
) -> dict[str, Any]:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    execution = json.loads(sandbox_proof_path.read_text(encoding="utf-8"))
    planned_intervention = plan["intervention"]["type"]
    executed_intervention = EXECUTED_INTERVENTIONS.get(execution["single_intervention"])
    plan_matches_execution = planned_intervention == executed_intervention
    proven = bool(
        plan_matches_execution
        and execution["same_checkpoint"]
        and execution["proven"]
        and execution["control"]["invariant"] == "PASS"
        and execution["counterfactual"]["invariant"] == "FAIL"
    )
    seed = f"{file_hash(plan_path)}:{file_hash(sandbox_proof_path)}"
    proof = {
        "experiment_id": f"px_{hashlib.sha256(seed.encode()).hexdigest()[:12]}",
        "verdict": "PROVEN" if proven else "NOT_PROVEN",
        "model_role": "hypothesis_only",
        "model": plan["model"],
        "model_usage": plan.get("usage", {}),
        "hypothesis": plan["hypothesis"],
        "branch_point": plan["branch_point"],
        "invariant": plan["target_invariant"],
        "planned_intervention": planned_intervention,
        "executed_intervention": executed_intervention,
        "plan_matches_execution": plan_matches_execution,
        "same_checkpoint": execution["same_checkpoint"],
        "checkpoint_uuid": execution["checkpoint_uuid"],
        "control": execution["control"],
        "counterfactual": execution["counterfactual"],
        "sources": {
            "experiment_plan": file_hash(plan_path),
            "sandbox_execution": file_hash(sandbox_proof_path),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    return proof
