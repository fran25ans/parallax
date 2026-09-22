from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from .experiment import CounterfactualExperiment
from .evidence import verify_evidence_bundle
from .nebius_sandbox import (
    run_live_sandbox_smoke,
    run_live_stock_race_experiment,
    run_live_ticketshop_experiment,
    sandbox_smoke_plan,
    stock_race_sandbox_plan,
    ticketshop_sandbox_plan,
)
from .nemotron import (
    DEFAULT_MODEL,
    INTERVENTION_CAPABILITIES,
    design_experiment_live,
    experiment_designer_prompt,
)
from .proof import assemble_counterfactual_proof
from .static_catalog import write_static_catalog


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="parallax", description="Find the timeline where your application breaks."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    demo = subcommands.add_parser("demo", help="Run the TicketShop counterfactual experiment")
    demo.add_argument("--output", type=Path, help="Directory for run state and evidence")
    verify = subcommands.add_parser("verify", help="Verify an evidence bundle")
    verify.add_argument("evidence", type=Path)
    sandbox = subcommands.add_parser(
        "sandbox-smoke", help="Validate Nebius checkpoint branching"
    )
    sandbox.add_argument(
        "--live", action="store_true", help="Create one checkpoint and two live branches"
    )
    sandbox.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/nebius-sandbox-smoke.json"),
    )
    experiment = subcommands.add_parser(
        "sandbox-experiment", help="Run TicketShop in two Nebius timelines"
    )
    experiment.add_argument("--live", action="store_true")
    experiment.add_argument(
        "--scenario", choices=("payment-retry", "stock-race"), default="payment-retry"
    )
    experiment.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/nebius-ticketshop-proof.json"),
    )
    experiment.add_argument(
        "--plan",
        type=Path,
        help="Validated Nemotron plan whose selected capability will be executed",
    )
    design = subcommands.add_parser(
        "design-experiment", help="Ask Nemotron to select one counterfactual"
    )
    design.add_argument("--live", action="store_true")
    design.add_argument(
        "--scenario", choices=("payment-retry", "stock-race"), default="payment-retry"
    )
    design.add_argument("--model", default=DEFAULT_MODEL)
    design.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/nemotron-experiment-plan.json"),
    )
    assemble = subcommands.add_parser(
        "assemble-proof", help="Combine a Nemotron plan with Sandbox evidence"
    )
    assemble.add_argument(
        "--plan",
        type=Path,
        default=Path("evidence/nemotron-experiment-plan.json"),
    )
    assemble.add_argument(
        "--execution",
        type=Path,
        default=Path("evidence/nebius-ticketshop-proof.json"),
    )
    assemble.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/counterfactual-proof.json"),
    )
    static_catalog = subcommands.add_parser(
        "static-catalog", help="Build the read-only proof catalog for GitHub Pages"
    )
    static_catalog.add_argument(
        "--evidence", type=Path, default=Path("evidence")
    )
    static_catalog.add_argument(
        "--output", type=Path, default=Path("web/public/proofs.json")
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    if arguments.command == "verify":
        valid, failures = verify_evidence_bundle(arguments.evidence)
        print("EVIDENCE BUNDLE: " + ("VERIFIED" if valid else "INVALID"))
        for failure in failures:
            print(f"- {failure}")
        return 0 if valid else 1

    if arguments.command == "sandbox-smoke":
        if not arguments.live:
            print("NEBIUS SANDBOX SMOKE PLAN / NO REMOTE OPERATIONS")
            for index, step in enumerate(sandbox_smoke_plan(), start=1):
                print(f"{index}. {step}")
            return 0
        try:
            proof = run_live_sandbox_smoke(arguments.output)
        except RuntimeError as error:
            print(f"NEBIUS SANDBOX SMOKE BLOCKED: {error}")
            return 1
        print("NEBIUS SANDBOX BRANCHING: VERIFIED")
        print(f"Checkpoint: {proof.checkpoint_uuid}")
        for branch in proof.branches:
            print(f"{branch.name}: {branch.result_uuid}")
        print(f"Evidence: {arguments.output}")
        return 0

    if arguments.command == "sandbox-experiment":
        selected_intervention = None
        if arguments.plan:
            try:
                plan_payload = json.loads(arguments.plan.read_text(encoding="utf-8"))
                selected_intervention = plan_payload["intervention"]["type"]
            except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
                print(f"NEBIUS EXPERIMENT BLOCKED: invalid plan: {error}")
                return 1
            if (
                not isinstance(selected_intervention, str)
                or selected_intervention not in INTERVENTION_CAPABILITIES
            ):
                print("NEBIUS EXPERIMENT BLOCKED: plan selected an unknown capability")
                return 1
        if not arguments.live:
            plan = (
                stock_race_sandbox_plan()
                if arguments.scenario == "stock-race"
                else ticketshop_sandbox_plan()
            )
            print(f"NEBIUS {arguments.scenario.upper()} PLAN / NO REMOTE OPERATIONS")
            for index, step in enumerate(plan, start=1):
                print(f"{index}. {step}")
            if selected_intervention:
                print(f"Selected capability: {selected_intervention}")
            return 0
        try:
            proof = (
                run_live_stock_race_experiment(
                    arguments.output,
                    intervention=selected_intervention
                    or "interleave_two_actors_after_read",
                )
                if arguments.scenario == "stock-race"
                else run_live_ticketshop_experiment(
                    arguments.output,
                    intervention=selected_intervention
                    or "drop_response_after_commit",
                )
            )
        except RuntimeError as error:
            print(f"NEBIUS TICKETSHOP EXPERIMENT BLOCKED: {error}")
            return 1
        print("NEBIUS COUNTERFACTUAL EXPERIMENT")
        metric = "sold_count" if arguments.scenario == "stock-race" else "payment_count"
        print(f"Control:        {proof.control[metric]} / {proof.control['invariant']}")
        print(f"Counterfactual: {proof.counterfactual[metric]} / {proof.counterfactual['invariant']}")
        print("CAUSAL COUNTEREXAMPLE: " + ("PROVEN" if proof.proven else "NOT PROVEN"))
        print(f"Evidence: {arguments.output}")
        return 0 if proof.proven else 1

    if arguments.command == "design-experiment":
        if not arguments.live:
            prompt = experiment_designer_prompt(arguments.scenario)
            print("NEMOTRON EXPERIMENT DESIGN / NO INFERENCE")
            print(f"Model: {arguments.model}")
            print("Planner: generic application-manifest planner")
            print("Maximum completion tokens: 1600")
            print("Candidate interventions: 6")
            print("Calls: 0")
            print("Prompt characters:", len(prompt))
            return 0
        try:
            plan = design_experiment_live(
                arguments.output,
                model=arguments.model,
                scenario=arguments.scenario,
            )
        except (RuntimeError, ValueError) as error:
            print(f"NEMOTRON EXPERIMENT DESIGN BLOCKED: {error}")
            return 1
        print("NEMOTRON EXPERIMENT PLAN: VALIDATED")
        print(f"Branch point:  {plan.branch_point}")
        print(f"Intervention:  {plan.intervention['type']}")
        print(f"Invariant:     {plan.target_invariant}")
        print(f"Observable:    {plan.expected_observable}")
        print("Ranked:        " + " > ".join(
            candidate["type"] for candidate in plan.ranked_candidates
        ))
        print(f"Model:         {plan.model}")
        print(f"Total tokens:  {plan.usage.get('total_tokens', 'not reported')}")
        print(f"Evidence: {arguments.output}")
        return 0

    if arguments.command == "assemble-proof":
        proof = assemble_counterfactual_proof(
            arguments.plan, arguments.execution, arguments.output
        )
        metric = "payment_count" if "payment_count" in proof["control"] else "sold_count"
        unit = "payment" if metric == "payment_count" else "sale"
        print("PARALLAX COUNTERFACTUAL PROOF")
        print(f"Experiment:       {proof['experiment_id']}")
        print(f"Nemotron role:    {proof['model_role']}")
        print(f"Plan matched:     {proof['plan_matches_execution']}")
        print(
            "Control:          "
            f"{proof['control'][metric]} {unit} / "
            f"{proof['control']['invariant']}"
        )
        print(
            "Counterfactual:   "
            f"{proof['counterfactual'][metric]} {unit}s / "
            f"{proof['counterfactual']['invariant']}"
        )
        print(f"VERDICT:          {proof['verdict']}")
        print(f"Evidence: {arguments.output}")
        return 0 if proof["verdict"] == "PROVEN" else 1

    if arguments.command == "static-catalog":
        write_static_catalog(arguments.evidence, arguments.output)
        print(f"STATIC PROOF CATALOG: {arguments.output}")
        return 0

    output = arguments.output or Path(tempfile.mkdtemp(prefix="parallax-"))
    outcome = CounterfactualExperiment(output).run()
    proof = outcome.proof

    print("PARALLAX COUNTERFACTUAL PROOF")
    print(f"Experiment:        {proof.experiment_id}")
    print(f"Same checkpoint:   {'YES' if proof.same_initial_state else 'NO'}")
    print(f"Changed variable:  {proof.changed_variable}")
    print()
    print("TIMELINE A / CONTROL")
    print(f"  payments:         {proof.control.state['payment_count']}")
    print(f"  tickets:          {proof.control.state['ticket_count']}")
    print(f"  {proof.control.invariant_id}:          {proof.control.invariant_status}")
    print()
    print("TIMELINE B / RESPONSE LOST")
    print(f"  payments:         {proof.counterfactual.state['payment_count']}")
    print(f"  tickets:          {proof.counterfactual.state['ticket_count']}")
    print(f"  {proof.counterfactual.invariant_id}:          {proof.counterfactual.invariant_status}")
    print()
    print("CAUSAL COUNTEREXAMPLE: " + ("PROVEN" if proof.proven else "NOT PROVEN"))
    print(
        "REGRESSION REPRODUCTION: "
        + ("VERIFIED" if proof.regression_reproduced else "FAILED")
    )
    print(f"Evidence: {outcome.evidence_directory}")
    return 0 if proof.proven else 1


if __name__ == "__main__":
    raise SystemExit(main())
