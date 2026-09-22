# PARALLAX

**Your app works in this timeline. PARALLAX finds the timeline where it breaks.**

PARALLAX is a counterfactual bug laboratory. It begins with one known application
state, forks that state into isolated timelines, changes one event, and lets
deterministic invariants decide whether the alternate history exposed a real bug.

## Counterfactual Control Deck

The deck renders the real assembled proof from
`evidence/counterfactual-proof.json`. It does not simulate findings or call
Nebius while the UI is open.

Install the local web dependencies once:

```bash
.venv/bin/pip install -e '.[web]'
cd web && npm install && cd ..
```

Run the read-only evidence API and the deck in separate terminals:

```bash
.venv/bin/uvicorn parallax.api:app --host 127.0.0.1 --port 8810
```

```bash
cd web
npm run dev
```

Open `http://127.0.0.1:5173/`, then play or scrub the synchronized replay.
The UI performs no paid model or Sandbox operations.

This first technical spike demonstrates a checkout idempotency failure:

```text
                    SAME CHECKPOINT
                          |
              +-----------+-----------+
              |                       |
         CONTROL                  RESPONSE LOST
              |                       |
        payment committed        payment committed
        response delivered       response lost
              |                  client retries
              |                  payment committed
              |                       |
       1 payment / PASS          2 payments / FAIL
```

The verifier, not an LLM, decides whether the experiment is proven. A proof requires:

1. Both branches started from the same checkpoint hash.
2. Exactly one declared intervention changed.
3. The control branch passed the invariant.
4. The counterfactual branch failed the invariant.

## Hackathon baseline

PARALLAX v0.1 demonstrates two distinct failure classes:

- `PAY-001`: a temporal retry after a response is lost following commit creates
  a duplicate payment.
- `STOCK-001`: two buyers interleaved after reading the final stock unit sell
  the same ticket twice.

Both experiments were proposed by Nemotron Super, executed in branches created
from a Nebius Sandbox checkpoint, and verified by deterministic invariants.
See [BASELINE.md](BASELINE.md) for evidence hashes and the acceptance record.

## Run the proof

No external services or paid APIs are needed for this spike.

```bash
cd parallax
PYTHONPATH=src python3 -m parallax demo --output evidence/runs/local-demo
```

Expected result:

```text
TIMELINE A / CONTROL
  payments:         1
  PAY-001:          PASS

TIMELINE B / RESPONSE LOST
  payments:         2
  PAY-001:          FAIL

CAUSAL COUNTEREXAMPLE: PROVEN
REGRESSION REPRODUCTION: VERIFIED
```

Verify that the evidence bundle has not changed:

```bash
PYTHONPATH=src python3 -m parallax verify evidence/runs/local-demo/evidence
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Current boundary

This commit validates the counterfactual engine locally using copied SQLite
checkpoints. Nebius Sandbox checkpoint/fork semantics and Nemotron experiment
design are the next integration milestones. The project does not yet claim that
the local copy mechanism is equivalent to a live VM checkpoint.

## Nebius Sandbox safety gate

Preview the exact smoke-test plan without making a remote call:

```bash
PYTHONPATH=src python3 -m parallax sandbox-smoke
```

A live run requires both the Nebius optional dependency and an explicit,
temporary spend switch. It is intentionally limited to one checkpoint and two
small BusyBox branches and no model inference:

```bash
PARALLAX_ALLOW_NEBIUS_SPEND=true \
  PYTHONPATH=src python3 -m parallax sandbox-smoke --live
```

The local `.env.local` file must contain both `NEBIUS_API_KEY` and
`NEBIUS_PROJECT_ID`. Neither value is included in evidence or logs.

After the branching smoke test succeeds, preview or execute the real TicketShop
counterfactual experiment:

```bash
PYTHONPATH=src python3 -m parallax sandbox-experiment

PARALLAX_ALLOW_NEBIUS_SPEND=true \
  PYTHONPATH=src python3 -m parallax sandbox-experiment --live
```

Nemotron experiment design is a separate, bounded step. Dry-run first; the live
command makes exactly one request with a 500-token completion ceiling:

```bash
PYTHONPATH=src python3 -m parallax design-experiment

PARALLAX_ALLOW_NEBIUS_SPEND=true \
  PYTHONPATH=src python3 -m parallax design-experiment --live
```

Combine the validated hypothesis and the deterministic Sandbox result without
making another remote call:

```bash
PYTHONPATH=src python3 -m parallax assemble-proof
```
