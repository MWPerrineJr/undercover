# Pilot plan

## Goal and scope

Build the claims pilot in `docs/SPEC.md` from the existing health-check skeleton. Handlers can view the queue and complete claim records, run the UnderCover Agent, follow its activity, read its instructions and sign off payouts over $1,000. The agent reads the customer's claim, documents, policy and history through the backend, decides approve, decline or refer, and gives a payout calculation and a two- or three-sentence explanation citing the relevant policy section.

Use FastAPI and SQLite, LangChain `create_agent` on OpenRouter, and React/Vite with strict TypeScript. Keep the existing root installation, development and check commands. The default model is `openai/gpt-6-luna` with low reasoning effort; honor `MODEL_NAME`, including `openrouter/free`, and read `OPENROUTER_API_KEY` from `.env`.

The pilot uses policy wording alone, without the claims manual or manual-only business rules. Seed only the six named business JSON files and `policy_wording.md`; do not scan data directories. Do not open or serve `data/evals/`, import held-out claims or security fixtures, or use answer keys to write prompts or tests. There is no sign-in, real payment, customer messaging, AWS work, harness build, swarm, evaluation runner or durable agent checkpointing.

## Design decisions

- SQLite owns claim workflow, decisions, simulated payments, handler sign-offs and recorded activity. Seed missing business records on startup without overwriting work on later starts. Use an ignored local database and isolated temporary databases in tests.
- Distinguish workflow status from decision and payment status. Map seeded `open` claims to `waiting`. Starting a run moves a claim to `in_progress`; decline and refer finish as `decided`. Approved payouts of $1,000 or less finish after simulated payment. Approved payouts above $1,000 become `waiting_for_sign_off`, then `decided` after sign-off and payment. Display the four workflow labels in plain English.
- Record a structured decision with outcome, USD payout, calculation, explanation and policy sections. Declined and referred claims have zero payout. Use decimal arithmetic or integer cents for money, including the approval-limit comparison.
- Keep decision, sign-off and payment as separate API operations. The payment operation requires an amount, checks it against the stored approved payout, and blocks amounts over $1,000 until a valid handler has signed off that exact decision. The agent cannot create a handler sign-off through its tools. This is workflow enforcement in an app without authentication, not an identity-security boundary.
- Start one claim at a time per run using a FastAPI background task and an atomic claim-state check. The HTTP start request returns promptly; handlers can start other waiting claims. Use a new thread ID for each run and correlate persisted activity with that ID. Do not introduce a separate worker service.
- The agent's business reads, instructions and writes go through HTTP API tools; it never opens data files or SQLite. Backend orchestration records tool activity and outcomes as they happen. Display concise operational events, not hidden model reasoning. Poll the API while a run is active rather than introducing streaming infrastructure.
- Store one backend-owned instruction text, served read only to both the agent and dashboard, with the current policy wording and plan information available through explicit backend reads. Only the wording supplies claim-handling rules; company settings supply the $1,000 payment gate. Do not expose manual-only settings as decision rules.
- Reject duplicate starts and invalid transitions with `409`, missing records with `404`, and malformed inputs with `422`. If a run fails before a decision is saved, record the failure and return it to waiting for an explicit retry. If a decision or payment has already been saved, preserve it and show the remaining action without starting a second adjudication.

## Phase 1: Persist the business records

Establish the data layer first so every later feature uses the same records and survives backend restarts. Keep the SQLite schema and seed loader small; retain source fields needed to display a claim in full.

Build typed models and storage for company settings, plans, customers with history, policies, handlers, claims and policy wording. Add workflow, decision, sign-off, payment and activity storage with database constraints for their relationships. Keep `GET /api/health` working.

Success criteria:

- [x] A fresh temporary database contains exactly the 25 queue claims from `data/claims.json`, all initially waiting, with resolvable policy, customer and plan relationships and the three handlers.
- [x] Backend tests compare stored claim stories, all items and document text, policy dates/add-ons/travelers, customer history and policy wording against the allowed source files without reading evaluation files.
- [x] Restarting initialization neither duplicates records nor overwrites a changed claim state, decision or recorded activity; tests verify both behaviors.
- [x] Seed-loader tests prove that only the explicit allowed files are opened, excluding the claims manual, evaluation and security folders.
- [x] `uv run pytest -q` passes with temporary database isolation; `GET /api/health` still returns `200` and `{"status":"ok"}`.
- [x] Python formatting, lint, types and the existing coverage threshold pass through `npm run check:python`.

## Phase 2: Claims API and payment enforcement

Put the business invariant in the backend before connecting a model. Expose small operations that the dashboard and agent can share, with payment separate from decision recording.

Planned API contract (all under `/api`):

| Operation | Route | Result |
| --- | --- | --- |
| List queue | `GET /claims` | Claim summaries and workflow, decision and payment states |
| Read claim | `GET /claims/{claim_id}` | Complete claim and stored decision, sign-off and payment |
| Read policy/customer | `GET /policies/{policy_id}`, `GET /customers/{customer_id}` | Policy record and customer record including history |
| Read plans/wording | `GET /plans`, `GET /policy-wording` | Plan benefits/add-ons and wording with version |
| Read instructions | `GET /instructions` | Exact instruction text used by the agent |
| List handlers | `GET /handlers` | Handlers available to sign off |
| Read activity | `GET /claims/{claim_id}/activity` | Ordered events with run/thread ID and timestamps |
| Record decision | `POST /claims/{claim_id}/decision` | Validated decision for the active run |
| Sign off | `POST /claims/{claim_id}/sign-off` | Handler ID recorded against the current approved decision |
| Pay claim | `POST /claims/{claim_id}/payment` | One simulated payment for the explicitly supplied amount |

Every operation has a unique `operation_id`, one-line docstring and fully required inputs. Mutation inputs identify the active run or current decision as appropriate, preventing stale writes. No generic filesystem, SQL, evaluation or instruction-editing API is needed.

Success criteria:

- [ ] API tests and direct requests show `GET /api/claims` returning 25 summaries and `GET /api/claims/CLM-1001` returning its full story, items and document text; linked policy, customer/history, plans and wording endpoints return the corresponding records.
- [ ] Every OpenAPI operation has a unique explicit operation ID, a one-line route docstring and no optional path, query or body inputs; malformed decisions and missing records return `422` and `404` respectively.
- [ ] Synthetic-fixture tests verify approve, decline and refer, required explanations/citations/calculations, zero payout for non-approvals, rejection of negative/non-finite/fractional-cent amounts, and rejection of decisions outside an active run.
- [ ] A $1,000.00 approval can be paid without sign-off. A $1,000.01 approval remains waiting for sign-off, and a direct payment request is rejected with `409` before sign-off, leaving no payment record.
- [ ] A valid handler sign-off permits the exact approved amount through the separate payment operation. Unknown or ineligible handlers, stale decision sign-offs, mismatched amounts, non-approved claims and repeated payments cannot create a payment.
- [ ] Transaction tests show concurrent payment attempts cannot create two payments or bypass sign-off; repeated/stale decision writes cannot replace a completed decision or invalidate a payment.
- [ ] `npm run check:python` passes with the payment boundary and transition tests included and coverage at least 80%.

## Phase 3: The agent and visible runs

Connect `run(claim_id, thread_id)` to backend-only tools using LangChain `create_agent`. Keep model injection for tests. Fetch the instructions from the backend before building the agent; tools read the claim and linked evidence and write the decision and simulated payment.

Instructions require reading the full evidence and customer history, applying wording limits, exclusions, add-ons, offsets and deductibles, citing sections, and referring when the available evidence cannot support a decision. They must not invent missing facts or import manual-only rules. For an over-limit approval, save the approval and leave payment for handler sign-off.

Add `POST /api/claims/{claim_id}/run`, returning `202` with a thread ID. Backend orchestration records start, tool calls, concise results, decision, payment/sign-off requirement, completion and errors. The run endpoint and activity writes follow the same required-input and OpenAPI conventions. Never record API keys in activity.

Success criteria:

- [ ] Stub-model tests exercise a complete tool sequence: instructions, claim, policy, customer history, plans/wording, decision and payment. They verify that the agent reaches business records only through the backend API.
- [ ] Scripted approve, decline and refer runs persist their structured outcomes and policy citations. A normal approval pays once; an approval over $1,000 stops at waiting for sign-off.
- [ ] A stub agent that attempts an over-limit payment before sign-off receives the backend rejection, with no payment written; enforcement does not depend on obeying the prompt.
- [ ] `POST /api/claims/CLM-1001/run` returns `202` promptly with a thread ID. A controlled delayed stub exposes `in_progress` and intermediate ordered activity through GET requests before it finishes.
- [ ] Concurrent duplicate start requests yield one accepted run and one `409`. Starting a decided or sign-off-pending claim is rejected without overwriting its decision.
- [ ] Failure tests cover an unavailable backend/model, invalid tool output and interrupted work: visible failure activity is retained, retry is possible before decision recording, and saved decisions/payments are preserved afterward. Recovery instructions cover an in-process run interrupted by server restart without automatic model reruns.
- [ ] Unit tests verify the default model and low reasoning effort, the `MODEL_NAME` override and instruction retrieval. All tests use stubs and make no OpenRouter requests.
- [ ] `npm run check:python` passes with at least 80% coverage.

## Phase 4: Handler dashboard

Replace the health page with the claims workspace. Build the read views and action controls against the established API so the interface reflects persisted backend state.

Show the queue with identifiers, customer, claim type, claimed amount and workflow status. Selecting a claim opens its complete story, items, document text, policy/plan/add-ons and customer history, alongside the decision, calculation, cited policy sections, payment and sign-off. Include Run agent, an activity view that refreshes during work, a handler selector and sign-off/payment controls, and a read-only instructions view. Signing off records approval first, then requests the separate payment operation; if payment fails, retain sign-off and offer payment retry.

Use the brand fonts, rounded panels, light and dark surfaces, specified colors and US-dollar formatting. Keep labels plain, statuses readable without color, keyboard controls accessible, and layouts usable on narrow screens.

Success criteria:

- [ ] Vitest/Testing Library tests cover queue loading, claim selection, complete evidence and decision display, instructions, empty/loading/error states, and stale-request handling when switching claims.
- [ ] Component tests verify active-run polling, terminal-state polling cleanup, disabled duplicate-run controls, over-limit sign-off controls and payment retry after a saved sign-off.
- [ ] A handler can choose one of the three seeded handlers, sign off an approved over-limit payout and see the simulated payment and decided status. Declined and referred claims have no payment action.
- [ ] Using the Playwright MCP server, inspect the queue, full claim, live activity, over-limit sign-off and instructions pages with the stubbed backend, at desktop and mobile widths and in both color modes; verify keyboard navigation and readable focus/status/error feedback.
- [ ] Browser inspection confirms Instrument Sans, Instrument Serif where an accent is used, JetBrains Mono for numbers/IDs, brand surfaces/colors, and currency such as `$1,250.00`, without clipped documents or horizontal page overflow.
- [ ] `npm run check:ts` passes with strict TypeScript, no `any`, and at least 80% Vitest coverage.

## Phase 5: End-to-end workflows

Prove the complete system works through the browser, including the payment boundary. Run real backend operations against an isolated seeded test database and a deterministic stub model; use synthetic decisions rather than evaluation answers. Keep test-only model selection out of normal production API inputs.

Success criteria:

- [ ] Playwright tests load all 25 queue claims, open a complete claim, read policy/history/documents, and confirm the displayed instructions match the backend's instruction text.
- [ ] An approval at or below $1,000 moves from waiting through visible in-progress activity to decided and paid, with calculation and policy citation visible after refresh.
- [ ] An approval above $1,000 reaches waiting for sign-off with no payment. A direct pre-sign-off API payment attempt fails, then a handler signs off in the UI and exactly one simulated payment completes the claim.
- [ ] Separate decline and refer journeys finish as decided with reasons/citations and no payment. A failed run displays an error and can be retried without duplicate decisions or payments.
- [ ] Refreshing or restarting the backend preserves decisions, activity, sign-offs and payments; tests or a documented restart check verify this against the same temporary database.
- [ ] E2E setup resets only its isolated database and does not modify development data, read evaluation files or call a real model. The suite is repeatable without a key, including when a development server is already running.
- [ ] `npm run e2e` passes, followed by `npm run check` passing all Python, TypeScript and Playwright checks without lowering thresholds or disabling rules.

## Phase 6: Operational handover

Finish the instructions and verify the pilot from the documented commands. Keep the handover short and honest about the pilot's limits: stub tests prove workflow and safeguards, while model decision accuracy is not measured against handler answers in this build.

Success criteria:

- [ ] From the repo root, `uv sync` and `npm install` succeed and install the pre-commit hook; `npm run dev` starts both services on macOS and uses scripts compatible with Windows, with no new shell-specific commands.
- [ ] `docs/STATUS.md` describes what is built, startup URLs, `.env` variables, database location/initialization, safe local reset instructions, run/retry and interrupted-run recovery, handler sign-off, simulated payments and all check commands. Update the short README only where needed.
- [ ] Browser checks using Playwright MCP confirm the documented queue, claim, activity, instructions and sign-off workflows, including the visible distinction between an approved decision and an unpaid payout awaiting sign-off.
- [ ] Final `npm run check` passes: ruff formatting/lint, pyright, pytest with at least 80% coverage, Prettier, ESLint, tsc, Vitest with at least 80% coverage, and Playwright. Record actual results in `docs/STATUS.md`.
- [ ] No secrets, local databases, evaluation answers or unrelated student changes are included in commits. No resources have been created on AWS and nothing has been pushed.

## Implementation process

This is a plan only; implementation starts when requested. Implement all six phases in order. For each phase, add tests, verify and tick every success criterion, update `docs/STATUS.md`, and commit the phase with the pre-commit hook enabled. Fix failures before continuing; never skip hooks, lower thresholds or disable rules. If a required rule appears wrong, stop and ask as `docs/PROCESS.md` requires. Run the complete check suite before handing over the finished pilot.
