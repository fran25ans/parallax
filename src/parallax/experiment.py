from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from .evidence import sha256_file, write_evidence_bundle
from .invariants import PAYMENT_ONCE, Invariant
from .models import (
    BranchResult,
    CounterfactualProof,
    Event,
    Intervention,
    InterventionType,
    InvariantStatus,
)
from .ticketshop import ResponseLost, TicketShop, create_checkpoint
from .regression import compile_payment_regression, run_generated_regression


@dataclass(frozen=True)
class ExperimentOutcome:
    proof: CounterfactualProof
    evidence_directory: Path


class CounterfactualExperiment:
    def __init__(self, workspace: Path, invariant: Invariant = PAYMENT_ONCE) -> None:
        self.workspace = workspace
        self.invariant = invariant

    def run(self) -> ExperimentOutcome:
        self.workspace.mkdir(parents=True, exist_ok=True)
        checkpoint = self.workspace / "checkpoint" / "ticketshop.sqlite3"
        create_checkpoint(checkpoint)
        checkpoint_hash = sha256_file(checkpoint)

        control_db = self._fork(checkpoint, "control")
        counterfactual_db = self._fork(checkpoint, "response-lost")
        same_initial_state = (
            sha256_file(control_db) == checkpoint_hash == sha256_file(counterfactual_db)
        )

        control = self._run_control(control_db, checkpoint_hash)
        counterfactual = self._run_response_loss(counterfactual_db, checkpoint_hash)
        single_intervention = self._single_intervention_changed(control, counterfactual)
        proven = (
            same_initial_state
            and single_intervention
            and control.invariant_status == InvariantStatus.PASS
            and counterfactual.invariant_status == InvariantStatus.FAIL
        )

        experiment_seed = f"{checkpoint_hash}:{counterfactual.intervention.type}"
        experiment_id = f"px_{hashlib.sha256(experiment_seed.encode()).hexdigest()[:12]}"
        regression = run_generated_regression(
            compile_payment_regression(), self.workspace
        )
        proof = CounterfactualProof(
            experiment_id=experiment_id,
            base_checkpoint=checkpoint_hash,
            control=control,
            counterfactual=counterfactual,
            same_initial_state=same_initial_state,
            single_intervention=single_intervention,
            proven=proven,
            changed_variable="response_after_commit=LOST",
            minimal_trace=[
                "POST /checkout",
                "COMMIT payment",
                "DROP response",
                "RETRY POST /checkout",
                "COMMIT duplicate payment",
            ],
            regression_test="generated-test.py",
            regression_reproduced=regression.reproduced,
            regression_exit_code=regression.exit_code,
        )
        evidence_directory = write_evidence_bundle(
            proof, self.workspace / "evidence", regression
        )
        return ExperimentOutcome(proof=proof, evidence_directory=evidence_directory)

    def _fork(self, checkpoint: Path, branch: str) -> Path:
        destination = self.workspace / "branches" / branch / "ticketshop.sqlite3"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(checkpoint, destination)
        return destination

    def _run_control(self, database: Path, checkpoint_hash: str) -> BranchResult:
        events: list[Event] = []
        shop = TicketShop(database)
        shop.checkout("cart-001", events)
        state = shop.snapshot("cart-001")
        return BranchResult(
            name="control",
            checkpoint_hash=checkpoint_hash,
            intervention=Intervention(type=InterventionType.NONE),
            events=events,
            state=state,
            invariant_status=self.invariant.check(state),
            invariant_id=self.invariant.id,
        )

    def _run_response_loss(self, database: Path, checkpoint_hash: str) -> BranchResult:
        events: list[Event] = []
        shop = TicketShop(database)
        try:
            shop.checkout(
                "cart-001",
                events,
                intervention=InterventionType.DROP_RESPONSE_AFTER_COMMIT,
            )
        except ResponseLost:
            events.append(
                Event(
                    sequence=len(events) + 1,
                    type="client.retry_scheduled",
                    detail={"reason": "no_acknowledgement"},
                )
            )
            shop.checkout("cart-001", events)

        state = shop.snapshot("cart-001")
        return BranchResult(
            name="response-lost",
            checkpoint_hash=checkpoint_hash,
            intervention=Intervention(
                type=InterventionType.DROP_RESPONSE_AFTER_COMMIT,
                at_event="after_payment_commit",
            ),
            events=events,
            state=state,
            invariant_status=self.invariant.check(state),
            invariant_id=self.invariant.id,
        )

    @staticmethod
    def _single_intervention_changed(
        control: BranchResult, counterfactual: BranchResult
    ) -> bool:
        return (
            control.checkpoint_hash == counterfactual.checkpoint_hash
            and control.intervention.type == InterventionType.NONE
            and counterfactual.intervention.type
            == InterventionType.DROP_RESPONSE_AFTER_COMMIT
        )
