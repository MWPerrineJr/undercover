import { useState } from "react";
import { api } from "./api";
import { label, money } from "./format";
import type { QueueRun, Summary } from "./types";

function QueueRunner({
  progress,
  waiting,
  refresh,
}: Readonly<{
  progress: QueueRun | null;
  waiting: number;
  refresh: () => void;
}>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function start() {
    setBusy(true);
    setError("");
    try {
      await api("/queue/run", undefined, {});
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Unable to run the queue.",
      );
    } finally {
      setBusy(false);
      refresh();
    }
  }
  return (
    <div className="queue-runner">
      <button
        disabled={busy || !progress || progress.running || waiting === 0}
        onClick={() => {
          void start();
        }}
      >
        {progress?.running ? "Queue running" : "Run queue"}
      </button>
      <p className="muted">
        {waiting} waiting · Runs one claim at a time using OpenRouter.
      </p>
      {progress && progress.total > 0 && (
        <div className="queue-progress" role="status">
          <p>{progress.message}</p>
          <progress
            value={progress.processed}
            max={progress.total}
            aria-label="Queue progress"
          />
          <p>
            {progress.processed} of {progress.total} attempted ·{" "}
            {progress.failed} failed · {progress.skipped} skipped
          </p>
          {progress.current_claim_id && (
            <p>Reviewing {progress.current_claim_id}</p>
          )}
        </div>
      )}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}

interface Props {
  claims: Summary[] | null;
  progress: QueueRun | null;
  finished: boolean;
  error: string;
  selected: string;
  refresh: () => void;
  select: (id: string) => void;
}
export function Queue({
  claims,
  progress,
  finished,
  error,
  selected,
  refresh,
  select,
}: Readonly<Props>) {
  const visible = claims?.filter(
    (claim) => (claim.status === "decided") === finished,
  );
  const waiting =
    claims?.filter((claim) => claim.status === "waiting").length ?? 0;
  return (
    <aside className="queue panel">
      <div className="section-heading">
        <h2>{finished ? "Finished claims" : "Claims queue"}</h2>
        <span className="queue-count">{visible?.length ?? "—"}</span>
      </div>
      <QueueRunner progress={progress} waiting={waiting} refresh={refresh} />
      {error && (
        <p role="alert">
          {error} <button onClick={refresh}>Retry</button>
        </p>
      )}
      {!claims && !error && <p role="status">Loading queue…</p>}
      {visible?.length === 0 && (
        <p>
          {finished ? "No finished claims yet." : "No claims in the queue."}
        </p>
      )}
      <nav aria-label="Claims">
        {visible?.map((claim) => (
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
            <span className="queue-amount">
              Claimed {money(claim.amount_claimed)}
            </span>
            {claim.decision && (
              <span className="queue-result">
                {label(claim.decision.outcome)} · {money(claim.decision.payout)}
              </span>
            )}
          </button>
        ))}
      </nav>
    </aside>
  );
}
