import { useCallback, useEffect, useState } from "react";
import { api, useResource } from "./api";
import { ClaimDetail } from "./ClaimDetail";
import { label, money } from "./format";
import type { Summary } from "./types";
import "./style.css";

const loadQueue = (signal: AbortSignal) => api<Summary[]>("/claims", signal);
const loadInstructions = (signal: AbortSignal) =>
  api<{ text: string }>("/instructions", signal);

function Instructions({ revision }: Readonly<{ revision: number }>) {
  const { data, error } = useResource(loadInstructions, revision);
  return (
    <section className="panel instructions">
      <p className="eyebrow">Read only</p>
      <h1>Agent instructions</h1>
      <p>The instructions used by the UnderCover Agent for every claim.</p>
      <pre>{data?.text ?? (error || "Loading instructions…")}</pre>
    </section>
  );
}

interface QueueProps {
  queue: Summary[] | null;
  error: string;
  selected: string;
  refresh: () => void;
  select: (id: string) => void;
}
function Queue({
  queue,
  error,
  selected,
  refresh,
  select,
}: Readonly<QueueProps>) {
  return (
    <aside className="queue panel">
      <div className="section-heading">
        <h2>Claims queue</h2>
        <span className="queue-count">{queue?.length ?? "—"}</span>
      </div>
      <p className="muted">Your team's claims, in one place.</p>
      {error && (
        <p role="alert">
          {error} <button onClick={refresh}>Retry</button>
        </p>
      )}
      {!queue && !error && <p role="status">Loading queue…</p>}
      {queue?.length === 0 && <p>No claims in the queue.</p>}
      <nav aria-label="Claims">
        {queue?.map((claim) => (
          <button
            key={claim.claim_id}
            className={`queue-item ${selected === claim.claim_id ? "selected" : ""}`}
            aria-current={selected === claim.claim_id ? "true" : undefined}
            onClick={() => {
              select(claim.claim_id);
            }}
          >
            <span className="queue-item-top">
              <span className="identifier">{claim.claim_id}</span>
              <span className={`badge ${claim.status}`}>
                {label(claim.status)}
              </span>
            </span>
            <strong>{claim.customer_name}</strong>
            <span>{label(claim.claim_type)}</span>
            <span className="queue-amount">{money(claim.amount_claimed)}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}

export function App() {
  const [revision, setRevision] = useState(0);
  const [selection, setSelection] = useState<string | null>(null);
  const [instructions, setInstructions] = useState(false);
  const { data: queue, error } = useResource(loadQueue, revision);
  const refresh = useCallback(() => {
    setRevision((value) => value + 1);
  }, []);
  const running = queue?.some((claim) => claim.running) ?? false;
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(refresh, 1000);
    return () => {
      clearInterval(timer);
    };
  }, [running, refresh]);
  const selected = selection ?? queue?.[0]?.claim_id ?? "";
  let content = (
    <section className="panel">
      <h1>Claims workspace</h1>
      <p>Select a claim to review its evidence and decision.</p>
    </section>
  );
  if (selected)
    content = (
      <ClaimDetail
        key={selected}
        id={selected}
        revision={revision}
        refresh={refresh}
      />
    );
  if (instructions) content = <Instructions revision={revision} />;
  return (
    <div className="workspace">
      <header className="topbar">
        <a href="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            u
          </span>
          <span>
            UnderCover<small>TRAVEL INSURANCE</small>
          </span>
        </a>
        <span className="tagline">Care for every journey.</span>
        <button
          className="secondary"
          aria-pressed={instructions}
          onClick={() => {
            setInstructions((value) => !value);
          }}
        >
          {instructions ? "Claims workspace" : "Agent instructions"}
        </button>
      </header>
      <div className="workspace-body">
        <Queue
          queue={queue}
          error={error}
          selected={selected}
          refresh={refresh}
          select={(id) => {
            setSelection(id);
            setInstructions(false);
          }}
        />
        <main>{content}</main>
      </div>
      <footer>Pilot workspace · All payments are simulated · USD</footer>
    </div>
  );
}
