from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import live_nebius_spend_allowed, nebius_api_key


TOKEN_FACTORY_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"
ALLOWED_INTERVENTIONS = {
    "delay_response",
    "drop_response_after_commit",
    "duplicate_request",
    "interleave_two_buyers_after_stock_read",
}
KNOWN_INVARIANTS = {"PAY-001", "STOCK-001"}


@dataclass(frozen=True)
class ExperimentPlan:
    branch_point: str
    intervention: dict[str, Any]
    hypothesis: str
    target_invariant: str
    reason: str
    model: str
    usage: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def experiment_designer_prompt() -> str:
    return """You are PARALLAX Experiment Designer.

Select exactly one controlled intervention that is worth testing. You propose a
hypothesis only; deterministic execution will decide whether a bug exists.

Application context:
- POST /checkout reads a cart, inserts a payment, inserts a ticket if absent,
  commits the database transaction, and then returns HTTP 200.
- The client retries POST /checkout if it receives no acknowledgement.
- No idempotency key or duplicate-payment constraint is visible.
- Baseline trace: request -> payment commit -> HTTP 200.

Invariant:
- PAY-001: A cart can produce at most one successful payment.

Allowed interventions:
- delay_response
- drop_response_after_commit
- duplicate_request

Return one JSON object only, with exactly this shape:
{
  "branch_point": "string",
  "intervention": {"type": "one allowed intervention"},
  "hypothesis": "string",
  "target_invariant": "PAY-001",
  "reason": "string"
}
"""


def stock_experiment_designer_prompt() -> str:
    return """You are PARALLAX Experiment Designer.

Select exactly one controlled concurrency intervention worth testing. You only
propose a hypothesis; deterministic execution decides whether a bug exists.

Application context:
- One ticket remains in inventory.
- A purchase reads the available quantity, then inserts a sale and decrements stock.
- The availability check and write are not protected by a lock or atomic constraint.
- Baseline trace: buyer A reads stock=1 -> commits one sale -> stock=0.

Invariant:
- STOCK-001: The final ticket can be sold at most once and stock never goes below zero.

Allowed intervention:
- interleave_two_buyers_after_stock_read

Return one JSON object only, with exactly this shape:
{
  "branch_point": "string",
  "intervention": {"type": "interleave_two_buyers_after_stock_read"},
  "hypothesis": "string",
  "target_invariant": "STOCK-001",
  "reason": "string"
}
"""


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
    required = {"branch_point", "intervention", "hypothesis", "target_invariant", "reason"}
    if set(payload) != required:
        raise ValueError("Nemotron response does not match the experiment-plan schema")
    intervention = payload["intervention"]
    if not isinstance(intervention, dict) or set(intervention) != {"type"}:
        raise ValueError("Intervention must contain only a type")
    if intervention["type"] not in ALLOWED_INTERVENTIONS:
        raise ValueError("Nemotron selected an intervention outside the allowlist")
    if expected_invariant not in KNOWN_INVARIANTS:
        raise ValueError("Parser was configured with an unknown invariant")
    if payload["target_invariant"] != expected_invariant:
        raise ValueError("Nemotron selected an unknown invariant")
    for field in ("branch_point", "hypothesis", "reason"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"Nemotron returned an invalid {field}")
    return ExperimentPlan(
        branch_point=payload["branch_point"],
        intervention=intervention,
        hypothesis=payload["hypothesis"],
        target_invariant=payload["target_invariant"],
        reason=payload["reason"],
        model=model,
        usage={key: int(value) for key, value in usage.items() if isinstance(value, int)},
    )


def design_experiment_live(output: Path, model: str = DEFAULT_MODEL) -> ExperimentPlan:
    return _design_experiment_live(
        output,
        prompt=experiment_designer_prompt(),
        expected_invariant="PAY-001",
        model=model,
    )


def design_stock_experiment_live(
    output: Path, model: str = DEFAULT_MODEL
) -> ExperimentPlan:
    return _design_experiment_live(
        output,
        prompt=stock_experiment_designer_prompt(),
        expected_invariant="STOCK-001",
        model=model,
    )


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
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 500,
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
