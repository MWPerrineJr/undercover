import { useState } from "react";
import { api } from "./api";
import { claimState, label, money } from "./format";
import { TodoList } from "./TodoList";
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
  const [cap, setCap] = useState("5");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const running = progress?.status === "running";
  const done =
    progress?.todos.filter((todo) => todo.state === "done").length ?? 0;
  const left =
    progress?.todos.filter((todo) => todo.state === "left_for_handler")
      .length ?? 0;
  async function start() {
    setBusy(true);
    setError("");
    try {
      await api("/queue/run", undefined, { cap: Number(cap) });
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
      <div className="queue-start">
        <label htmlFor="cap">Claims in this run</label>
        <input
          id="cap"
          type="number"
          min={1}
          value={cap}
          disabled={running}
          onChange={(event) => {
            setCap(event.target.value);
          }}
        />
        <button
          disabled={
            busy || !progress || running || waiting === 0 || !Number(cap)
          }
          onClick={() => {
            void start();
          }}
        >
          {running ? "Queue running" : "Run queue"}
        </button>
      </div>
      <p className="muted">
        {waiting} waiting · The agent plans the run and gives each claim to a
        fresh agent.
      </p>
      {progress?.run_id && (
        <div className="queue-progress" role="status">
          <p>{label(progress.status)}</p>
          <progress
            value={done + left}
            max={Math.max(progress.todos.length, progress.cap)}
            aria-label="Queue progress"
          />
          <p>
            {done} of {progress.cap} done · {left} left for a handler
          </p>
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
      {!finished && (
        <>
          <QueueRunner
            progress={progress}
            waiting={waiting}
            refresh={refresh}
          />
          <TodoList progress={progress} />
        </>
      )}
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
              <span className={`badge ${claimState(claim)}`}>
                {label(claimState(claim))}
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
