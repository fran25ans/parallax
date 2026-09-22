from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import live_nebius_spend_allowed, nebius_api_key


TOKEN_FACTORY_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"

INTERVENTION_CAPABILITIES = {
    "delay_response": "Delay an acknowledgement without changing committed state.",
    "drop_response_after_commit": "Lose a response after the operation commits.",
    "duplicate_request": "Repeat the same request with identical input.",
    "interleave_two_actors_after_read": "Pause after a read and interleave a second actor.",
    "reorder_independent_events": "Reverse two events declared independent by the trace.",
    "no_intervention": "Keep the observed execution unchanged as a negative control.",
}

SCENARIO_MANIFESTS: dict[str, dict[str, Any]] = {
    "payment-retry": {
        "system": "TicketShop checkout",
        "invariant": {
            "id": "PAY-001",
            "statement": "A cart can produce at most one successful payment.",
        },
        "operations": [
            "POST /checkout reads the cart.",
            "The handler inserts a payment and commits the transaction.",
            "The handler returns an acknowledgement after the commit.",
            "A client without an acknowledgement may retry the same checkout.",
        ],
        "observed_trace": [
            "request accepted",
            "payment committed",
            "HTTP 200 delivered",
        ],
        "observable_fields": ["payment_count", "ticket_count", "response_status"],
    },
    "stock-race": {
        "system": "Single-ticket inventory",
        "invariant": {
            "id": "STOCK-001",
            "statement": "The final ticket is sold at most once and stock never becomes negative.",
        },
        "operations": [
            "A purchase reads the available stock quantity.",
            "If stock is positive, it inserts a sale and decrements stock.",
            "The read, decision, sale insert and stock update are separate trace events.",
        ],
        "observed_trace": [
            "buyer A reads stock=1",
            "buyer A commits one sale",
            "stock becomes 0",
        ],
        "observable_fields": ["sold_count", "stock", "invariant"],
    },
}

KNOWN_INVARIANTS = {
    manifest["invariant"]["id"] for manifest in SCENARIO_MANIFESTS.values()
}


@dataclass(frozen=True)
class ExperimentPlan:
    branch_point: str
    intervention: dict[str, Any]
    hypothesis: str
    expected_observable: str
    target_invariant: str
    reason: str
    ranked_candidates: list[dict[str, Any]]
    model: str
    usage: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def scenario_manifest(scenario: str) -> dict[str, Any]:
    try:
        return SCENARIO_MANIFESTS[scenario]
    except KeyError as error:
        raise ValueError(f"Unknown scenario: {scenario}") from error


def experiment_designer_prompt(scenario: str = "payment-retry") -> str:
    manifest = scenario_manifest(scenario)
    capabilities = [
        {"type": name, "semantics": semantics}
        for name, semantics in INTERVENTION_CAPABILITIES.items()
    ]
    return f"""You are the PARALLAX Counterfactual Experiment Planner.

Read the application manifest and rank the three most useful supported
interventions for testing its security or reliability invariant. Select the
highest-ranked candidate. Do not claim that a bug exists: deterministic branch
execution will decide that. A plausible but harmless intervention is preferable
to inventing an unsupported capability.

APPLICATION MANIFEST
{json.dumps(manifest, indent=2)}

SUPPORTED INTERVENTION CAPABILITIES
{json.dumps(capabilities, indent=2)}

Return one JSON object only, with exactly this shape:
{{
  "branch_point": "an event present in the observed trace or operations",
  "intervention": {{"type": "one supported intervention type"}},
  "hypothesis": "a falsifiable statement",
  "expected_observable": "a measurable difference using observable_fields",
  "target_invariant": "{manifest['invariant']['id']}",
  "reason": "why the selected intervention is stronger than the alternatives",
  "ranked_candidates": [
    {{"type": "supported type", "score": 0.0, "rationale": "short reason"}},
    {{"type": "supported type", "score": 0.0, "rationale": "short reason"}},
    {{"type": "supported type", "score": 0.0, "rationale": "short reason"}}
  ]
}}

Scores must be numbers from 0 to 1 in descending order. Candidate types must be
unique and the selected intervention must equal the first ranked candidate.
"""


def stock_experiment_designer_prompt() -> str:
    """Compatibility wrapper; both scenarios use the same generic planner."""
    return experiment_designer_prompt("stock-race")


def parse_experiment_plan(
    content: str,
    model: str,
    usage: dict[str, int],
    expected_invariant: str = "PAY-001",
) -> ExperimentPlan:
    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Nemotron response did not contain a JSON object")
    payload = json.loads(content[start : end + 1])
    required = {
        "branch_point",
        "intervention",
        "hypothesis",
        "expected_observable",
        "target_invariant",
        "reason",
        "ranked_candidates",
    }
    if set(payload) != required:
        raise ValueError("Nemotron response does not match the experiment-plan schema")
    intervention = payload["intervention"]
    if not isinstance(intervention, dict) or set(intervention) != {"type"}:
        raise ValueError("Intervention must contain only a type")
    if intervention["type"] not in INTERVENTION_CAPABILITIES:
        raise ValueError("Nemotron selected an intervention outside the allowlist")
    if expected_invariant not in KNOWN_INVARIANTS:
        raise ValueError("Parser was configured with an unknown invariant")
    if payload["target_invariant"] != expected_invariant:
        raise ValueError("Nemotron selected an unknown invariant")
    for field in ("branch_point", "hypothesis", "expected_observable", "reason"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"Nemotron returned an invalid {field}")
    ranked = payload["ranked_candidates"]
    if not isinstance(ranked, list) or len(ranked) != 3:
        raise ValueError("Nemotron must rank exactly three candidates")
    candidate_types: list[str] = []
    previous_score = 1.0
    for candidate in ranked:
        if not isinstance(candidate, dict) or set(candidate) != {
            "type",
            "score",
            "rationale",
        }:
            raise ValueError("Nemotron returned an invalid ranked candidate")
        candidate_type = candidate["type"]
        score = candidate["score"]
        if candidate_type not in INTERVENTION_CAPABILITIES:
            raise ValueError("Nemotron ranked an intervention outside the allowlist")
        if candidate_type in candidate_types:
            raise ValueError("Nemotron ranked duplicate interventions")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise ValueError("Nemotron returned a non-numeric candidate score")
        if not 0 <= score <= 1 or score > previous_score:
            raise ValueError("Nemotron candidate scores must descend from 1 to 0")
        if not isinstance(candidate["rationale"], str) or not candidate["rationale"].strip():
            raise ValueError("Nemotron returned an invalid candidate rationale")
        candidate_types.append(candidate_type)
        previous_score = float(score)
    if candidate_types[0] != intervention["type"]:
        raise ValueError("Selected intervention must be the top-ranked candidate")
    return ExperimentPlan(
        branch_point=payload["branch_point"],
        intervention=intervention,
        hypothesis=payload["hypothesis"],
        expected_observable=payload["expected_observable"],
        target_invariant=payload["target_invariant"],
        reason=payload["reason"],
        ranked_candidates=ranked,
        model=model,
        usage={key: int(value) for key, value in usage.items() if isinstance(value, int)},
    )


def design_experiment_live(
    output: Path,
    model: str = DEFAULT_MODEL,
    scenario: str = "payment-retry",
) -> ExperimentPlan:
    manifest = scenario_manifest(scenario)
    return _design_experiment_live(
        output,
        prompt=experiment_designer_prompt(scenario),
        expected_invariant=manifest["invariant"]["id"],
        model=model,
    )


def design_stock_experiment_live(
    output: Path, model: str = DEFAULT_MODEL
) -> ExperimentPlan:
    """Compatibility wrapper; both scenarios use the same generic planner."""
    return design_experiment_live(output, model=model, scenario="stock-race")


def _design_experiment_live(
    output: Path,
    prompt: str,
    expected_invariant: str,
    model: str,
) -> ExperimentPlan:
    if not live_nebius_spend_allowed():
        raise RuntimeError(
            "Live Nemotron inference is disabled. Set "
            "PARALLAX_ALLOW_NEBIUS_SPEND=true for one intentional call."
        )
    try:
        import httpx
    except ImportError as error:
        raise RuntimeError("Install the Nebius optional dependencies first.") from error

    response = httpx.post(
        TOKEN_FACTORY_URL,
        headers={"Authorization": f"Bearer {nebius_api_key()}"},
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only the requested JSON object, with no markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 1600,
            "response_format": {"type": "json_object"},
        },
        timeout=60.0,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Token Factory returned HTTP {response.status_code}")
    payload = response.json()
    plan = parse_experiment_plan(
        payload["choices"][0]["message"]["content"],
        model=model,
        usage=payload.get("usage", {}),
        expected_invariant=expected_invariant,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan.to_dict(), indent=2) + "\n", encoding="utf-8")
    return plan
