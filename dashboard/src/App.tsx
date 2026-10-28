import { useState } from "react";
import { api, useResource } from "./api";
import { ClaimDetail } from "./ClaimDetail";
import { Queue } from "./Queue";
import { ResetDashboard } from "./ResetDashboard";
import { WorkspaceTabs } from "./WorkspaceTabs";
import { useWorkspace } from "./workspace";
import type { Instructions as InstructionText, WorkspaceTab } from "./types";
import "./style.css";

const loadInstructions = (signal: AbortSignal) =>
  api<InstructionText[]>("/instructions", signal);
function Instructions({ revision }: Readonly<{ revision: number }>) {
  const { data, error } = useResource(loadInstructions, revision);
  return (
    <section className="panel instructions">
      <p className="eyebrow">Read only</p>
      <h1>Agent instructions</h1>
      <p>The instructions the UnderCover Agent works to.</p>
      {data ? (
        data.map((instructions) => (
          <div key={instructions.name}>
            <h2>{instructions.title}</h2>
            <pre>{instructions.text}</pre>
          </div>
        ))
      ) : (
        <pre>{error || "Loading instructions…"}</pre>
      )}
    </section>
  );
}

export function App() {
  const [selection, setSelection] = useState<string | null>(null);
  const [instructions, setInstructions] = useState(false);
  const [tab, setTab] = useState<WorkspaceTab>("queue");
  const {
    claims,
    progress,
    total,
    finishedCount,
    queueCount,
    firstClaim,
    loading,
    error,
    revision,
    refresh,
    running,
  } = useWorkspace();
  const selected = selection ?? firstClaim;
  function changeTab(next: WorkspaceTab) {
    setTab(next);
    setInstructions(false);
    setSelection(
      claims?.find(
        (claim) => (claim.status === "decided") === (next === "finished"),
      )?.claim_id ?? "",
    );
  }
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
        refresh={() => {
          setSelection(selected);
          refresh();
        }}
      />
    );
  if (tab === "reset")
    content = (
      <ResetDashboard
        running={running || loading}
        total={total}
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
      <WorkspaceTabs
        tab={tab}
        queueCount={queueCount}
        finishedCount={finishedCount}
        select={changeTab}
      />
      <div
        className={`workspace-body ${tab === "reset" ? "reset-layout" : ""}`}
        id={`${tab}-panel`}
        role="tabpanel"
        aria-labelledby={`${tab}-tab`}
      >
        {tab !== "reset" && (
          <Queue
            claims={claims}
            progress={progress}
            finished={tab === "finished"}
            error={error}
            selected={selected}
            refresh={refresh}
            select={(id) => {
              setSelection(id);
              setInstructions(false);
            }}
          />
        )}
        <main>{content}</main>
      </div>
      <footer>Pilot workspace · All payments are simulated · USD</footer>
    </div>
  );
}
