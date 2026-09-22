# PARALLAX v0.1 - Hackathon Baseline

This baseline contains two independently executed counterfactual experiments.
Nemotron proposed each intervention, Nebius Sandboxes executed both branches
from one checkpoint, and PARALLAX applied deterministic invariants.

## Proven experiments

| Experiment | Failure class | Control | Counterfactual | Verdict |
| --- | --- | --- | --- | --- |
| PAY-001 | Temporal retry after lost response | 1 payment / PASS | 2 payments / FAIL | PROVEN |
| STOCK-001 | Interleaved stock race | 1 sale / PASS | 2 sales / FAIL | PROVEN |

## Evidence hashes

```text
PAY-001   f0580f9684f12bb3d24aa635ba6ea9b2cc4f44d76d3d51fcb63a4db352b6bac5
STOCK-001 e7653363d2c4b73178b3366294894d1f214ce07a1123c54ac3f95f73a5f68090
```

## Acceptance record

- 22 automated tests pass.
- The React production build completes successfully.
- Both plans match the interventions executed by Nebius.
- Both branches in each experiment share one checkpoint UUID.
- Credentials are excluded from evidence and ignored by Git.
- The Control Deck performs no paid calls during replay.
- Nemotron usage for the two plans: 1,185 total tokens.
- Nebius Sandbox usage for each proof: one checkpoint and two branches.

## Product boundary

PARALLAX v0.1 proves two failure classes. This baseline intentionally excludes
additional agents, retrieval systems, model orchestration, and extra scenarios.
Further work should focus on robustness, presentation, and submission quality.
