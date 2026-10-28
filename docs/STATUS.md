# Status

The pilot (`docs/PLAN.md`) and the harness (`docs/PLAN_HARNESS.md`) are both complete, each phase committed separately. The agent now organizes its own work: one run works the whole queue up to a cap, plans it as a to-do list the team can watch, hands each claim to a fresh subagent, looks up the sections of the wording and the manual it needs, and puts its own failures right.

## What is built

- FastAPI and SQLite with the 25 queue claims, full documents/items, policies, plans, customers/history and handlers. Startup seeds missing records without replacing saved work.
- The UnderCover Agent uses LangChain `create_agent` on OpenRouter. It reads instructions and business records only through HTTP tools and saves approve, decline or refer, a payout calculation, explanation and numbered citations.
- `agent/` is split into `api.py` (the backend client and instruction reads), `model.py` (the OpenRouter model), `tools.py` (the per-claim tools), `claim.py` (the claim agent) and `main.py` (the `run(claim_id, thread_id)` entry point). Each claim is worked by a fresh agent with its own message history, and `work_claim` reports the outcome in one line, such as `CLM-1002 approve $1,250.00 waiting for sign-off`.
- The agent looks the documents up rather than being handed them. `GET /api/documents` lists the 12 sections of the policy wording and the 14 sections of the claims manual, `GET /api/documents/search?q=` finds the sections that mention given words, and `GET /api/documents/{document}/sections/{number}` reads one section. Each read is recorded on the claim as activity of kind `read`.
- React/Vite dashboard with the queue, complete claim evidence, policy/plan and customer history, decisions, read-only instructions for both agents and live operational activity. Each claim page lists what the agent read, section by section, and the decision cites both wording and manual sections. Desktop/mobile layouts support light and dark modes.
- Separate decision, handler sign-off and simulated payment operations. Exactly $1,000 can be paid without sign-off; above $1,000 the backend blocks payment until a valid handler signs off. Payment must match the immutable decision and can be recorded only once.
- One run works the queue. `POST /api/queue/run` takes a cap and starts the queue agent, which calls `list_waiting_claims`, plans the run as a to-do list with `set_todo_list`, moves each item on with `update_todo`, hands each claim to a fresh claim agent with `work_one_claim` and closes with `finish_run`. The backend owns the cap: a claim taken beyond it is refused with 409. The queue page shows the cap, the to-do list and the closing summary; Queue and Finished tabs separate outstanding work from decided claims.
- A long run puts its own problems right. The claim-working tool never raises: a timeout or a provider error becomes a failure line. A claim that fails before a decision goes back to waiting with its attempt counted and can be tried again in the same run; after two attempts it is left for a handler, the backend refuses to start it again, and the queue and claim pages badge it. The cap counts distinct claims, so a retry costs no extra slot, and `finish_run` is refused while a claim inside the cap is still waiting.
- `uv run -m agent --cap 5` starts a capped run and `uv run -m agent --claim CLM-1001` works one named claim, both through the API.
- Reset tab clears workflow results and activity after an exact `RESET` confirmation, while retaining source records. Both the API and dashboard block resets during any active batch or individual run.
- Background runs with duplicate-start protection, timestamped activity and explicit retry/restart recovery. No sign-in, real payments, customer messages, evaluation runner or AWS resources.

## Install and run

Use Python 3.12, uv and Node 26. From the repository root, on macOS or Windows:

```text
uv sync
npm install
npm run dev
```

Before running an agent, add `OPENROUTER_API_KEY` to the root `.env`. `.env.example` lists the supported settings; preserve existing keys if `.env` already exists.

- Dashboard: http://localhost:5173
- Backend health: http://localhost:8000/api/health
- API reference: http://localhost:8000/docs

`npm install` installs the pre-commit hook and Playwright Chromium. `npm run dev` starts both services and watches backend and agent Python code. Stop both with Ctrl+C.

The default model is `deepseek/deepseek-v4.1-flash` with low reasoning effort. Set `MODEL_NAME` to override it, for example `openrouter/free`; the default reasoning setting is omitted for an override. `BACKEND_URL` defaults to http://localhost:8000 and configures the agent's HTTP client and Vite's backend proxy.

## Use it

In Queue, select a claim, inspect its documents and history, and choose Run agent for that claim alone. To work the queue, set Claims in this run and choose Run queue. The queue agent plans the run itself, chooses the order and gives each claim to a fresh claim agent, on the backend and using model API credits; it continues if you close the browser. Claims beyond the cap stay waiting. `uv run -m agent --cap 5` and `uv run -m agent --claim CLM-1001` do the same from the command line.

The to-do list under the run control fills in as the agent plans and ticks off as it works, each item carrying the claim agent's one-line report. When the run closes, its summary for the handlers appears there. The queue moves through waiting, in progress, waiting for sign-off and decided; a claim that failed twice is badged "left for a handler". Activity refreshes while a run is active and shows tool operations, the sections read, decisions, sign-off and simulated payments rather than hidden model reasoning.

Finished lists decided claims with their outcomes and payouts; select an entry to inspect its full evidence, what the agent read and its activity. Approvals awaiting sign-off stay in Queue until payment completes.

Approvals of $1,000 or less are paid by the agent through the separate payment API. Above $1,000, select a handler and choose Sign off and pay. If payment fails after sign-off, the sign-off is retained and Record payment retries only payment. Decline and refer finish without a payment. Referral means a handler needs to exercise judgment or obtain evidence; the pilot does not send customer messages.

Agent instructions shows the backend-owned texts the agent works to, read only. Decisions follow the policy wording as the claims manual says to read it; the agent looks up the sections it needs and cites them in `policy_sections` and `manual_sections`. The instructions are written from those two documents and never from `data/evals/`.

## Persistence and recovery

The default database is `undercover.sqlite3` in the repo root, ignored by git. Set `UNDERCOVER_DB` to choose another file in an existing directory. Only `company.json`, `plans.json`, `policies.json`, `customers.json`, `handlers.json`, `claims.json`, `policy_wording.md` and `claims_manual.md` seed the database. Evaluation/held-out claims and security fixtures are not loaded.

If a run fails before saving a decision, its activity records the failure and the claim returns to waiting. Check the key/model and backend configuration, then select Run agent to retry. Model or connection failures have a safe, generic activity message. A retry gets a new thread ID, while earlier activity remains visible.

If the backend stops during work, restart with `npm run dev`. Startup marks interrupted runs as stopped. Claims without decisions return to waiting; saved decisions, sign-offs and payments survive. An unpaid approval offers Record payment once any required sign-off is complete. An interrupted queue run is marked stopped, its to-do list is kept and any item left in progress returns to to-do; choose Run queue again to work the remaining waiting claims. There is no automatic model rerun or agent checkpoint resumption. A completed decision cannot be rerun or replaced through the API.

To start the pilot over, open Reset, type `RESET`, then choose Reset all claims. This permanently clears decisions, handler sign-offs, simulated payments, activity and batch progress, returning all claims to waiting. It retains source evidence, policies, customers/history, plans, handlers and model settings. Reset is blocked until all agents and the queue run have stopped. Opening the tab does not reset anything.

If you want to retain the entire database before resetting, stop the app and copy `undercover.sqlite3` (or the file selected by `UNDERCOVER_DB`) to a backup through your editor's file explorer.

`GET /api/queue` reads the current run with its to-do list, `POST /api/queue/run` takes `{"cap": n}` and returns HTTP 202, and `POST /api/queue/reset` takes `{"confirmation":"RESET"}`. The queue agent's own operations live under `/api/queue/{run_id}/`: `waiting`, `todos`, `todos/{claim_id}`, `claims/{claim_id}/start`, `claims/{claim_id}/finish` and `finish`. Conflicting starts, resets, a claim beyond the cap, a claim left for a handler and a close over a missed claim all return 409; missing or incorrect inputs return 422.

## Verification

`npm run check` passes on macOS with Node 26 and Python 3.12:

- Ruff formatting/lint and pyright: pass, zero type errors.
- Pytest: 64 tests pass, 99.4% total Python coverage (80% required).
- Prettier, ESLint and strict TypeScript: pass.
- Vitest: 18 tests pass, 100% statement coverage (80% required).
- Playwright: 11 tests pass, covering approval, direct over-limit payment rejection, handler sign-off, decline and referral, a failed run and its retry, keyboard focus, desktop and mobile layouts in both color modes, and a capped queue run whose to-do list fills in, retries a claim that failed once and ticks off, leaving the rest waiting.

No test calls a model. Browser tests start dedicated servers on ports 8010/5174 with a temporary database, and use the real agent loops with scripted models. No test reads `data/evals/`.

### The live run

After reseeding, one run capped at five claims on the default model (`deepseek/deepseek-v4.1-flash`) worked five claims on its own and left the other twenty waiting. The agent chose its own order (CLM-1001, CLM-1008, CLM-1011, CLM-1018, CLM-1010) rather than the queue's, and closed with a summary for the handlers:

- CLM-1001 approved $420.00 and paid, being at or below the $1,000 limit.
- CLM-1008 approved $2,240.00 and CLM-1011 approved $1,150.00, both held for a handler's sign-off.
- CLM-1010 declined, CLM-1018 referred.
- No claim was decided or paid twice, and no claim needed a second attempt.

On CLM-1001 the agent searched the documents four times and read eleven sections before deciding: wording 1, 3, 9, 10, 11 and 12, and manual 3, 5, 6, 7 and 8. It cited wording 1, 3, 9, 10, 11 and manual 4, 5, 6, 7, 9, 10, and applied the manual's rule that a delay on the way home extends cover to the extra day. The claim page lists every section it read.

The dashboard was checked with the Playwright MCP browser at 390px and 1440px in light and dark: the to-do list filling in and ticking off during the run, the summary at the end, the sections read on each claim page, no horizontal overflow and no console errors. That check found and fixed a crash on decisions saved before `manual_sections` existed.

Accuracy against the handlers' decisions in `data/evals/` has not been measured; that is for a later evaluation runner.

No thresholds or rules were weakened, no hooks were skipped and no changes were pushed.
