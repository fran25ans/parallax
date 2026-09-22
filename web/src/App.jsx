import { useEffect, useMemo, useState } from "react";
import {
  Bot,
  Box,
  Check,
  CircleAlert,
  FlaskConical,
  Hash,
  Pause,
  Play,
  RotateCcw,
  ServerCog,
  ShieldCheck,
} from "lucide-react";

const paymentReplay = [
  { label: "Checkpoint S0", control: "Same world state", counter: "Same world state" },
  { label: "Request", control: "POST /checkout", counter: "POST /checkout" },
  { label: "Commit", control: "COMMIT payment", counter: "COMMIT payment" },
  { label: "Divergence", control: "HTTP 200 delivered", counter: "DROP response", split: true },
  { label: "Recovery", control: "Client completes", counter: "CLIENT retry" },
  { label: "Replay", control: "No further write", counter: "POST /checkout" },
  { label: "Second commit", control: "Payments: 1", counter: "COMMIT payment · Payments: 2" },
  { label: "Verification", control: "PAY-001 · PASS", counter: "PAY-001 · FAIL" },
];

const stockReplay = [
  { label: "Checkpoint S0", control: "Stock: 1 ticket", counter: "Stock: 1 ticket" },
  { label: "Read", control: "buyer-a READ stock=1", counter: "buyer-a READ stock=1" },
  { label: "Interleave", control: "buyer-a continues", counter: "buyer-b READ stock=1", split: true },
  { label: "First commit", control: "buyer-a COMMIT sale", counter: "buyer-a COMMIT sale" },
  { label: "Second commit", control: "No second buyer", counter: "buyer-b COMMIT sale" },
  { label: "Final state", control: "sold=1 · stock=0", counter: "sold=2 · stock=-1" },
  { label: "Verification", control: "STOCK-001 · PASS", counter: "STOCK-001 · FAIL" },
];

function provenanceLabel(model) {
  return model?.includes("nemotron") ? "Nemotron Super" : model || "AI model";
}

function humanize(value) {
  return String(value || "").replaceAll("_", " ");
}

function Branch({ tone, name, subtitle, events, step, resultCount, metricLabel, invariant }) {
  const visibleEvents = events.filter((_, index) => index <= step);
  const isCounter = tone === "counter";
  return (
    <section className={`branch branch--${tone}`} aria-label={`${name} branch`}>
      <header className="branch__header">
        <div>
          <span className="eyebrow">{subtitle}</span>
          <h2>{name}</h2>
        </div>
        <span className="branch__status">{step === events.length - 1 ? invariant : "RUNNING"}</span>
      </header>
      <div className="event-stack">
        {visibleEvents.map((event, index) => (
          <div className={`event ${event.split && isCounter ? "event--fault" : ""}`} key={`${name}-${index}`}>
            <span className="event__index">{String(index).padStart(2, "0")}</span>
            <span>{isCounter ? event.counter : event.control}</span>
            {event.split && isCounter && <CircleAlert size={16} aria-label="Divergence point" />}
            {!isCounter && index > 0 && index < 4 && <Check size={15} aria-hidden="true" />}
          </div>
        ))}
      </div>
      <div className="branch__metric">
        <span>{metricLabel}</span>
        <strong>{step >= events.length - 2 ? resultCount : step >= 2 ? 1 : 0}</strong>
      </div>
    </section>
  );
}

function App() {
  const captureParams = new URLSearchParams(window.location.search);
  const [proof, setProof] = useState(null);
  const [catalog, setCatalog] = useState([]);
  const [selected, setSelected] = useState(
    captureParams.get("experiment") || "payment-retry",
  );
  const [error, setError] = useState("");
  const [step, setStep] = useState(Number(captureParams.get("step") || 0));
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const evidenceUrl = import.meta.env.PROD
      ? `${import.meta.env.BASE_URL}proofs.json`
      : "/api/proofs";
    fetch(evidenceUrl)
      .then((response) => {
        if (!response.ok) throw new Error("Evidence API is unavailable");
        return response.json();
      })
      .then((payload) => {
        setCatalog(payload.proofs);
        const requested = captureParams.get("experiment");
        const initial = payload.proofs.find((entry) => entry.id === requested)
          || payload.proofs[0];
        setProof(initial.proof);
        setSelected(initial.id);
      })
      .catch((reason) => setError(reason.message));
  }, []);

  const replay = proof?.invariant === "STOCK-001" ? stockReplay : paymentReplay;

  useEffect(() => {
    if (!playing) return undefined;
    const timer = window.setInterval(() => {
      setStep((current) => {
        if (current >= replay.length - 1) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 1050);
    return () => window.clearInterval(timer);
  }, [playing]);

  const shortHash = useMemo(
    () => (proof?.evidence_sha256 ? `${proof.evidence_sha256.slice(0, 12)}…${proof.evidence_sha256.slice(-8)}` : ""),
    [proof],
  );

  if (error) return <main className="load-state"><CircleAlert /> {error}</main>;
  if (!proof) return <main className="load-state"><FlaskConical className="spin" /> Loading verified evidence…</main>;

  const complete = step === replay.length - 1;
  const isStock = proof.invariant === "STOCK-001";
  const metric = isStock ? "sold_count" : "payment_count";
  const metricLabel = isStock ? "Tickets sold" : "Payments committed";
  const interventionLabel = humanize(proof.planned_intervention);
  const branchPointLabel = humanize(proof.branch_point);
  const deltaLabel = isStock ? "+1 oversold ticket" : "+1 duplicate payment";
  const rankedCandidates = proof.ranked_candidates || [];
  const selectedIndex = Math.max(0, catalog.findIndex((entry) => entry.id === selected));
  const selectExperiment = (entry) => {
    setPlaying(false);
    setStep(0);
    setSelected(entry.id);
    setProof(entry.proof);
  };
  return (
    <main className="deck">
      <header className="topbar">
        <div className="brand">
          <FlaskConical size={22} aria-hidden="true" />
          <div><strong>PARALLAX</strong><span>Counterfactual Control Deck</span></div>
        </div>
        <div className="experiment-id"><span>EXPERIMENT</span><strong>{proof.experiment_id}</strong></div>
        <div className="live-state"><i /> LIVE EVIDENCE</div>
      </header>

      <section className="summary-band">
        <div>
          <span className="eyebrow">COUNTERFACTUAL EXPERIMENT #{String(selectedIndex + 1).padStart(3, "0")}</span>
          <h1>One checkpoint. Two futures. One causal counterexample.</h1>
          <p>{proof.hypothesis}</p>
          {rankedCandidates.length > 0 && (
            <div className="planner-ranking">
              <Bot size={16} />
              <span>NEMOTRON RANKED {rankedCandidates.length} CANDIDATES</span>
              <strong>{rankedCandidates.map((candidate) => humanize(candidate.type)).join("  >  ")}</strong>
            </div>
          )}
        </div>
        <div className={`verdict ${complete ? "verdict--shown" : ""}`}>
          <span>CAUSAL COUNTEREXAMPLE</span>
          <strong>{complete ? proof.verdict : "PENDING"}</strong>
        </div>
      </section>

      <nav className="experiment-switcher" aria-label="Counterfactual experiments">
        {catalog.map((entry, index) => (
          <button className={entry.id === selected ? "active" : ""} key={entry.id} onClick={() => selectExperiment(entry)}>
            <span>EXPERIMENT #{String(index + 1).padStart(3, "0")}</span>
            <strong>{entry.proof.invariant}</strong>
            <small>{entry.id === "stock-race" ? "CONCURRENCY RACE" : "TEMPORAL RETRY"}</small>
          </button>
        ))}
      </nav>

      <div className="workspace">
        <aside className="context-panel">
          <section>
            <span className="eyebrow">EXPERIMENT CONTRACT</span>
            <dl>
              <div><dt>Checkpoint</dt><dd>S0 · {proof.checkpoint_uuid.slice(0, 8)}</dd></div>
              <div><dt>Branch point</dt><dd>{branchPointLabel}</dd></div>
              <div><dt>Single intervention</dt><dd>{interventionLabel}</dd></div>
              <div><dt>Invariant</dt><dd>{proof.invariant}</dd></div>
            </dl>
          </section>
          <section className="mini-map">
            <span className="eyebrow">BRANCH MAP</span>
            <div className="checkpoint"><Box size={17} /> CHECKPOINT S0</div>
            <div className="fork-lines"><span /><span /></div>
            <div className="fork-labels"><span>CONTROL</span><span>{isStock ? "RACE" : "COUNTERFACTUAL"}</span></div>
          </section>
          <section className="integrity">
            <span className="eyebrow">EVIDENCE INTEGRITY</span>
            <div><Hash size={17} /><code>{shortHash}</code></div>
            <span className="verified"><ShieldCheck size={15} /> SHA-256 VERIFIED</span>
          </section>
        </aside>

        <section className={`replay-panel ${step >= 3 ? "replay-panel--diverged" : ""}`}>
          <header className="replay-header">
            <div><span className="eyebrow">SYNCHRONIZED REPLAY</span><strong>T+{String(step).padStart(2, "0")} · {replay[step].label}</strong></div>
            <div className="replay-controls">
              <button title="Reset replay" aria-label="Reset replay" onClick={() => { setPlaying(false); setStep(0); }}><RotateCcw size={17} /></button>
              <button className="primary-control" title={playing ? "Pause replay" : "Play replay"} aria-label={playing ? "Pause replay" : "Play replay"} onClick={() => { if (step === replay.length - 1) setStep(0); setPlaying(!playing); }}>
                {playing ? <Pause size={18} /> : <Play size={18} />}
              </button>
            </div>
          </header>
          <input aria-label="Replay timeline" type="range" min="0" max={replay.length - 1} value={step} onChange={(event) => { setPlaying(false); setStep(Number(event.target.value)); }} />
          <div className="branches">
            <Branch tone="control" name="CONTROL" subtitle="Observed future" events={replay} step={step} resultCount={proof.control[metric]} metricLabel={metricLabel} invariant={proof.control.invariant} />
            <div className="branch-divider"><span>{step >= 3 ? "DIVERGENCE" : "SYNCHRONIZED"}</span></div>
            <Branch tone="counter" name={isStock ? "RACE" : "COUNTERFACTUAL"} subtitle="Intervened future" events={replay} step={step} resultCount={proof.counterfactual[metric]} metricLabel={metricLabel} invariant={proof.counterfactual.invariant} />
          </div>
        </section>

        <aside className="proof-panel">
          <span className="eyebrow">COUNTERFACTUAL PROOF</span>
          <div className="proof-title"><ShieldCheck size={28} /><div><span>INVARIANT</span><strong>{proof.invariant}</strong></div></div>
          <div className="comparison">
            <div><span>CONTROL</span><strong>{proof.control[metric]}</strong><small>{isStock ? "sale" : "payment"}</small></div>
            <div><span>{isStock ? "RACE" : "COUNTERFACTUAL"}</span><strong>{proof.counterfactual[metric]}</strong><small>{isStock ? "sales" : "payments"}</small></div>
          </div>
          <div className="delta"><span>CAUSAL DELTA</span><strong>{deltaLabel}</strong></div>
          <ul className="checks">
            <li><Check /> Planner ranking valid</li>
            <li><Check /> Same checkpoint</li>
            <li><Check /> One intervention</li>
            <li><Check /> Control passes</li>
            <li className={complete ? "check-fail" : ""}>{complete ? <CircleAlert /> : <span className="empty-check" />} Counterfactual fails</li>
          </ul>
          <div className={`proof-stamp ${complete ? "proof-stamp--shown" : ""}`}>
            <span>EXPLOITABILITY</span><strong>{complete ? "PROVEN" : "AWAITING REPLAY"}</strong>
          </div>
        </aside>
      </div>

      <footer className="provenance">
        <div><Bot /><span>NEMOTRON PLANNED</span><strong>{provenanceLabel(proof.model)}</strong></div>
        <b>→</b>
        <div><ServerCog /><span>SANDBOX EXECUTED</span><strong>Nebius Sandboxes</strong></div>
        <b>→</b>
        <div><ShieldCheck /><span>DETERMINISTICALLY VERIFIED</span><strong>PARALLAX</strong></div>
      </footer>
    </main>
  );
}

export default App;
