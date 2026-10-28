import { useCallback, useState } from "react";
import { api, loadDetails, useResource } from "./api";
import { RecordDetails } from "./RecordDetails";
import { claimState, label, money } from "./format";
import type { Details } from "./types";

interface Props {
  id: string;
  revision: number;
  refresh: () => void;
}

function useClaimAction(
  claim: Details["claim"],
  refresh: () => void,
  handler: string,
) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function act(action: "run" | "sign-off" | "payment") {
    setBusy(true);
    setError("");
    try {
      const base = `/claims/${claim.claim_id}`;
      if (action === "run") await api(`${base}/run`, undefined, {});
      if (action === "sign-off")
        await api(`${base}/sign-off`, undefined, {
          thread_id: claim.thread_id,
          handler_id: handler,
        });
      if (action !== "run")
        await api(`${base}/payment`, undefined, {
          thread_id: claim.thread_id,
          amount: claim.decision?.payout,
        });
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Action failed. Please retry.",
      );
    } finally {
      setBusy(false);
      refresh();
    }
  }

  return { busy, error, act };
}

function isPayable(claim: Details["claim"]) {
  return (
    claim.decision?.outcome === "approve" && !claim.payment && !claim.running
  );
}

function DecisionPanel({
  details,
  refresh,
}: Readonly<{
  details: Details;
  refresh: () => void;
}>) {
  const { claim, handlers } = details;
  const [handler, setHandler] = useState("HND-01");
  const { busy, error, act } = useClaimAction(claim, refresh, handler);
  const canPay = isPayable(claim);
  const needsSignOff =
    claim.status === "waiting_for_sign_off" && !claim.sign_off;
  return (
    <section className="panel decision-panel" aria-label="Decision">
      <div className="section-heading">
        <h2>Decision</h2>
        <span className={`badge ${claimState(claim)}`}>
          {label(claimState(claim))}
        </span>
      </div>
      {claim.decision ? (
        <>
          <p className="outcome">
            {label(claim.decision.outcome)}{" "}
            <strong>{money(claim.decision.payout)}</strong>
          </p>
          <p>{claim.decision.explanation}</p>
          <h3>Payout calculation</h3>
          <p className="calculation">{claim.decision.calculation}</p>
          <p>Policy sections {claim.decision.policy_sections.join(", ")}</p>
          {claim.decision.manual_sections.length > 0 && (
            <p>Manual sections {claim.decision.manual_sections.join(", ")}</p>
          )}
          {claim.sign_off && (
            <p>
              Signed off by{" "}
              {
                handlers.find(
                  (h) => h.handler_id === claim.sign_off?.handler_id,
                )?.name
              }
            </p>
          )}
          {claim.payment && (
            <p className="payment">
              Simulated payment recorded · {money(claim.payment.amount)}
            </p>
          )}
          {canPay && (
            <>
              {needsSignOff && (
                <>
                  <p>Payment is blocked until a handler signs off.</p>
                  <label htmlFor="handler">Signing handler</label>
                  <select
                    id="handler"
                    value={handler}
                    onChange={(e) => {
                      setHandler(e.target.value);
                    }}
                  >
                    {handlers
                      .filter((h) => h.can_approve_over_limit)
                      .map((h) => (
                        <option key={h.handler_id} value={h.handler_id}>
                          {h.name}
                        </option>
                      ))}
                  </select>
                </>
              )}
              <button
                disabled={busy}
                onClick={() => {
                  void act(needsSignOff ? "sign-off" : "payment");
                }}
              >
                {needsSignOff ? "Sign off and pay" : "Record payment"}
              </button>
            </>
          )}
        </>
      ) : (
        <>
          <p>
            {claim.running
              ? "The agent is reviewing the evidence. Follow its activity below."
              : "Ready for the UnderCover Agent to review the evidence."}
          </p>
          <button
            disabled={busy || claim.running}
            onClick={() => {
              void act("run");
            }}
          >
            {claim.running ? "Agent working" : "Run agent"}
          </button>
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

export function ClaimDetail({ id, revision, refresh }: Readonly<Props>) {
  const load = useCallback(
    (signal: AbortSignal) => loadDetails(id, signal),
    [id],
  );
  const { data, error } = useResource(load, revision);
  if (!data)
    return (
      <section className="panel" aria-live="polite">
        {error || "Loading claim…"}
        {error && <button onClick={refresh}>Retry</button>}
      </section>
    );
  const { claim, policy, customer, plans, wording, activity } = data;
  const plan = plans.plans.find((p) => p.plan === policy.plan);
  return (
    <article className="claim-detail" aria-label={`Claim ${id}`}>
      {error && (
        <p role="alert">
          {error} <button onClick={refresh}>Retry</button>
        </p>
      )}
      <header className="claim-header">
        <div>
          <p className="eyebrow">
            {id} · {label(claim.claim_type)}
          </p>
          <h1>{claim.summary}</h1>
          <p>
            {typeof customer.name === "string" ? customer.name : "Customer"} ·{" "}
            {claim.incident_location}
          </p>
        </div>
        <div className="claimed">
          <span>Amount claimed</span>
          <strong>{money(claim.amount_claimed)}</strong>
        </div>
      </header>
      <DecisionPanel details={data} refresh={refresh} />
      <section className="panel" aria-label="Agent activity">
        <h2>Agent activity</h2>
        {activity.length ? (
          <ol className="activity">
            {activity.map((event) => (
              <li key={event.id}>
                <time dateTime={event.created_at}>
                  {new Date(event.created_at).toLocaleTimeString("en-US")}
                </time>
                <span>{event.message}</span>
              </li>
            ))}
          </ol>
        ) : (
          <p>No activity yet.</p>
        )}
        {claim.thread_id && (
          <p className="muted identifier">Run {claim.thread_id}</p>
        )}
      </section>
      <section className="panel">
        <h2>The customer's account</h2>
        <p className="muted">
          Submitted {claim.submitted_on} · Incident {claim.incident_date}
        </p>
        <p className="story">{claim.story}</p>
        <h3>Items claimed</h3>
        <ul className="items">
          {claim.items.map((item, index) => (
            <li key={index}>
              <span>
                {item.description}
                <small>{label(item.category)}</small>
              </span>
              <strong>{money(item.amount)}</strong>
            </li>
          ))}
        </ul>
        <h3>Supporting documents</h3>
        {claim.documents.map((document, index) => (
          <details key={index} open>
            <summary>
              {document.name} <small>{label(document.type)}</small>
            </summary>
            <p className="document">{document.content}</p>
          </details>
        ))}
      </section>
      <section className="panel">
        <h2>Policy and plan</h2>
        <RecordDetails record={policy} />
        {plan && (
          <>
            <h3>Plan benefits</h3>
            <RecordDetails record={plan} />
          </>
        )}
        <h3>Deductible applies to</h3>
        <p>{plans.deductible_applies_to.map(label).join(", ")}</p>
        <h3>Available add-ons</h3>
        {plans.add_ons.map((addon, index) => (
          <RecordDetails key={index} record={addon} />
        ))}
      </section>
      <section className="panel">
        <h2>Customer and claim history</h2>
        <RecordDetails record={customer} />
      </section>
      <section className="panel">
        <details>
          <summary>Policy wording · {wording.version}</summary>
          <pre className="wording">{wording.text}</pre>
        </details>
      </section>
    </article>
  );
}
