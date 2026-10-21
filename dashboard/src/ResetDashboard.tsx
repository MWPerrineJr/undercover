import { useState } from "react";
import { api } from "./api";

interface Props {
  running: boolean;
  total: number;
  refresh: () => void;
}
export function ResetDashboard({ running, total, refresh }: Readonly<Props>) {
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState("");
  async function reset() {
    setBusy(true);
    setError("");
    setResult("");
    try {
      const response = await api<{ reset_claims: number }>(
        "/queue/reset",
        undefined,
        { confirmation },
      );
      setResult(`${String(response.reset_claims)} claims returned to waiting.`);
      setConfirmation("");
      refresh();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Reset failed. Please retry.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel reset-panel">
      <p className="eyebrow">Start over</p>
      <h1>Reset the pilot</h1>
      <p>
        Return all {total} claims to waiting. This permanently clears their
        decisions, handler sign-offs, simulated payments, agent activity and
        queue progress.
      </p>
      <p>
        Claim evidence, policies, customer records and model settings are
        retained.
      </p>
      {running && (
        <p role="status">
          Wait for all agents and the queue run to finish before resetting.
        </p>
      )}
      <label htmlFor="reset-confirmation">Type RESET to confirm</label>
      <input
        id="reset-confirmation"
        value={confirmation}
        autoComplete="off"
        onChange={(event) => {
          setConfirmation(event.target.value);
        }}
        disabled={running || busy}
      />
      <button
        className="danger"
        disabled={running || busy || confirmation !== "RESET"}
        onClick={() => {
          void reset();
        }}
      >
        {busy ? "Resetting…" : "Reset all claims"}
      </button>
      {error && <p role="alert">{error}</p>}
      {result && <p role="status">{result}</p>}
    </section>
  );
}
