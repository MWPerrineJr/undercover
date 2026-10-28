import type { KeyboardEvent } from "react";
import type { WorkspaceTab } from "./types";

interface Props {
  tab: WorkspaceTab;
  queueCount: number;
  finishedCount: number;
  select: (tab: WorkspaceTab) => void;
}
const tabs: WorkspaceTab[] = ["queue", "finished", "reset"];

export function WorkspaceTabs({
  tab,
  queueCount,
  finishedCount,
  select,
}: Readonly<Props>) {
  function navigate(event: KeyboardEvent<HTMLButtonElement>) {
    const offset = event.key === "ArrowRight" ? 1 : -1;
    if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    let next = tabs[(tabs.indexOf(tab) + offset + tabs.length) % tabs.length];
    if (event.key === "Home") next = "queue";
    if (event.key === "End") next = "reset";
    select(next);
    document.getElementById(`${next}-tab`)?.focus();
  }
  const labels = {
    queue: `Queue (${String(queueCount)})`,
    finished: `Finished (${String(finishedCount)})`,
    reset: "Reset",
  };
  return (
    <div
      className="workspace-tabs"
      role="tablist"
      aria-label="Claims workspace"
    >
      {tabs.map((value) => (
        <button
          role="tab"
          onKeyDown={navigate}
          id={`${value}-tab`}
          key={value}
          aria-selected={tab === value}
          aria-controls={`${value}-panel`}
          tabIndex={tab === value ? 0 : -1}
          onClick={() => {
            select(value);
          }}
        >
          {labels[value]}
        </button>
      ))}
    </div>
  );
}
