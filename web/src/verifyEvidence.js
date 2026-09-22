const encoder = new TextEncoder();

export async function sha256Hex(text) {
  const digest = await globalThis.crypto.subtle.digest("SHA-256", encoder.encode(text));
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function executedCapability(execution) {
  const value = execution.single_intervention || "";
  if (value.startsWith("capability=")) return value.slice("capability=".length);
  const legacy = {
    "response_after_commit=LOST": "drop_response_after_commit",
    "buyers_after_stock_read=INTERLEAVED": "interleave_two_actors_after_read",
  };
  return legacy[value] || null;
}

function check(id, label, passed, detail) {
  return { id, label, passed: Boolean(passed), detail };
}

function sameJson(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

export async function verifyEvidenceBundle({ proofText, planText, executionText, artifacts }) {
  const [proofHash, planHash, executionHash] = await Promise.all([
    sha256Hex(proofText),
    sha256Hex(planText),
    sha256Hex(executionText),
  ]);
  const proof = JSON.parse(proofText);
  const plan = JSON.parse(planText);
  const execution = JSON.parse(executionText);
  const planned = plan.intervention?.type;
  const executed = executedCapability(execution);
  const ranked = plan.ranked_candidates || [];

  const checks = [
    check("proof-hash", "Assembled proof hash", proofHash === artifacts.assembled_proof.sha256, proofHash),
    check("plan-hash", "Nemotron plan hash", planHash === artifacts.experiment_plan.sha256 && proof.sources?.experiment_plan === `sha256:${planHash}`, planHash),
    check("execution-hash", "Nebius execution hash", executionHash === artifacts.sandbox_execution.sha256 && proof.sources?.sandbox_execution === `sha256:${executionHash}`, executionHash),
    check("planner", "Planner ranking valid", ranked.length === 3 && ranked[0]?.type === planned && proof.planner_selection_valid === true && proof.invariant === plan.target_invariant && proof.hypothesis === plan.hypothesis, planned),
    check("intervention", "One planned intervention executed", Boolean(planned) && planned === executed && proof.planned_intervention === planned && proof.executed_intervention === executed, `${planned || "missing"} -> ${executed || "missing"}`),
    check("checkpoint", "Same checkpoint", execution.same_checkpoint === true && proof.same_checkpoint === true && proof.checkpoint_uuid === execution.checkpoint_uuid, execution.checkpoint_uuid),
    check("control", "Control preserves invariant", execution.control?.invariant === "PASS" && sameJson(proof.control, execution.control), execution.control?.invariant),
    check("counterfactual", "Counterfactual violates invariant", execution.counterfactual?.invariant === "FAIL" && sameJson(proof.counterfactual, execution.counterfactual), execution.counterfactual?.invariant),
  ];
  return {
    verified: checks.every((item) => item.passed) && proof.verdict === "PROVEN",
    checks,
    receipt: {
      experiment_id: proof.experiment_id,
      invariant: proof.invariant,
      verdict: proof.verdict,
      verified_at: new Date().toISOString(),
      hashes: { assembled_proof: proofHash, experiment_plan: planHash, sandbox_execution: executionHash },
      checks: Object.fromEntries(checks.map((item) => [item.id, item.passed])),
    },
  };
}
