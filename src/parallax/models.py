from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class InterventionType(StrEnum):
    NONE = "none"
    DROP_RESPONSE_AFTER_COMMIT = "drop_response_after_commit"
    DUPLICATE_REQUEST = "duplicate_request"


class InvariantStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class Intervention:
    type: InterventionType
    at_event: str | None = None


@dataclass(frozen=True)
class Event:
    sequence: int
    type: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BranchResult:
    name: str
    checkpoint_hash: str
    intervention: Intervention
    events: list[Event]
    state: dict[str, Any]
    invariant_status: InvariantStatus
    invariant_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CounterfactualProof:
    experiment_id: str
    base_checkpoint: str
    control: BranchResult
    counterfactual: BranchResult
    same_initial_state: bool
    single_intervention: bool
    proven: bool
    changed_variable: str
    minimal_trace: list[str]
    regression_test: str
    regression_reproduced: bool
    regression_exit_code: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
