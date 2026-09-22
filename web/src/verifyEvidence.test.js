import assert from "node:assert/strict";
import test from "node:test";
import { sha256Hex, verifyEvidenceBundle } from "./verifyEvidence.js";

function bundle() {
  const plan = {
    intervention: { type: "interleave_two_actors_after_read" },
    ranked_candidates: [
      { type: "interleave_two_actors_after_read" },
      { type: "delay_response" },
      { type: "duplicate_request" },
    ],
  };
  const execution = {
    checkpoint_uuid: "checkpoint-1",
    same_checkpoint: true,
    single_intervention: "capability=interleave_two_actors_after_read",
    control: { invariant: "PASS" },
    counterfactual: { invariant: "FAIL" },
  };
  return { plan, execution };
}

async function inputs(mutator = () => {}) {
  const { plan, execution } = bundle();
  plan.target_invariant = "TEST-001";
  plan.hypothesis = "A controlled hypothesis.";
  mutator(plan, execution);
  const planText = JSON.stringify(plan);
  const executionText = JSON.stringify(execution);
  const proof = {
    experiment_id: "px_test",
    invariant: "TEST-001",
    hypothesis: "A controlled hypothesis.",
    verdict: "PROVEN",
    planner_selection_valid: true,
    planned_intervention: plan.intervention.type,
    executed_intervention: "interleave_two_actors_after_read",
    same_checkpoint: true,
    checkpoint_uuid: "checkpoint-1",
    control: { invariant: "PASS" },
    counterfactual: { invariant: "FAIL" },
    sources: {
      experiment_plan: `sha256:${await sha256Hex(planText)}`,
      sandbox_execution: `sha256:${await sha256Hex(executionText)}`,
    },
  };
  const proofText = JSON.stringify(proof);
  return {
    proofText,
    planText,
    executionText,
    artifacts: {
      assembled_proof: { sha256: await sha256Hex(proofText) },
      experiment_plan: { sha256: await sha256Hex(planText) },
      sandbox_execution: { sha256: await sha256Hex(executionText) },
    },
  };
}

test("verifies an intact evidence bundle", async () => {
  const result = await verifyEvidenceBundle(await inputs());
  assert.equal(result.verified, true);
  assert.equal(result.checks.every((item) => item.passed), true);
});

test("fails closed when execution evidence is tampered", async () => {
  const data = await inputs();
  data.executionText = data.executionText.replace('"FAIL"', '"PASS"');
  const result = await verifyEvidenceBundle(data);
  assert.equal(result.verified, false);
  assert.equal(result.checks.find((item) => item.id === "execution-hash").passed, false);
  assert.equal(result.checks.find((item) => item.id === "counterfactual").passed, false);
});

test("fails closed when the executed intervention differs", async () => {
  const data = await inputs((_, execution) => {
    execution.single_intervention = "capability=delay_response";
  });
  const result = await verifyEvidenceBundle(data);
  assert.equal(result.verified, false);
  assert.equal(result.checks.find((item) => item.id === "intervention").passed, false);
});
