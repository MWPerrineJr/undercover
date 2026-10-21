# Status

The pilot is complete. All six phases in `docs/PLAN.md` were committed separately. The requested queue runner, finished-claims view and Reset tab are described in `docs/QUEUE.md`.

## What is built

- FastAPI and SQLite with the 25 queue claims, full documents/items, policies, plans, customers/history and handlers. Startup seeds missing records without replacing saved work.
- The UnderCover Agent uses LangChain `create_agent` on OpenRouter. It reads instructions and business records only through HTTP tools and saves approve, decline or refer, a payout calculation, explanation and numbered policy citations.
- React/Vite dashboard with the queue, complete claim evidence, policy/plan and customer history, decisions, read-only instructions and live operational activity. Desktop/mobile layouts support light and dark modes.
- Separate decision, handler sign-off and simulated payment operations. Exactly $1,000 can be paid without sign-off; above $1,000 the backend blocks payment until a valid handler signs off. Payment must match the immutable decision and can be recorded only once.
- Run queue processes a snapshot of waiting claims sequentially, continues after claim failures, prevents duplicate batches and persists progress. Queue and Finished tabs separate outstanding work from decided claims; list entries show decisions and payouts.
- Reset tab clears workflow results and activity after an exact `RESET` confirmation, while retaining source records. Both the API and dashboard block resets during any active batch or individual run.
- Background runs with duplicate-start protection, timestamped activity and explicit retry/restart recovery. No sign-in, real payments, customer messages, claims manual, evaluation runner or AWS resources.

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

The default model is `openai/gpt-6-luna` with low reasoning effort. Set `MODEL_NAME` to override it, for example `openrouter/free`; the default reasoning setting is omitted for an override. `BACKEND_URL` defaults to http://localhost:8000 and configures the agent's HTTP client and Vite's backend proxy.

## Use the pilot

In Queue, select a claim, inspect its documents and history, and choose Run agent. To process every waiting claim, choose Run queue. It runs on the backend one claim at a time using the configured OpenRouter model, and continues if you close the browser. This uses model API credits. Each snapshot claim is attempted once; failed claims stay waiting for an explicit retry. Already running or decided claims are skipped. The queue moves through waiting, in progress, waiting for sign-off and decided. Activity refreshes while a run is active and shows tool operations/results, decisions, sign-off and simulated payments rather than hidden model reasoning.

Batch progress shows attempts, failures, skipped claims and the current claim, and survives page refreshes. Finished lists decided claims with their outcomes and payouts; select an entry to inspect its full evidence and activity. Approvals awaiting sign-off stay in Queue until payment completes.

Approvals of $1,000 or less are paid by the agent through the separate payment API. Above $1,000, select a handler and choose Sign off and pay. If payment fails after sign-off, the sign-off is retained and Record payment retries only payment. Decline and refer finish without a payment. Referral means a handler needs to exercise judgment or obtain evidence; the pilot does not send customer messages.

Agent instructions shows the exact backend-owned text fetched for each new run, read only. Decisions use policy wording alone. Customer history is available as evidence, but manual-only handling rules are not added to the prompt or API.

## Persistence and recovery

The default database is `undercover.sqlite3` in the repo root, ignored by git. Set `UNDERCOVER_DB` to choose another file in an existing directory. Only `company.json`, `plans.json`, `policies.json`, `customers.json`, `handlers.json`, `claims.json` and `policy_wording.md` seed the database. Evaluation/held-out claims, security fixtures and the claims manual are not loaded.

If a run fails before saving a decision, its activity records the failure and the claim returns to waiting. Check the key/model and backend configuration, then select Run agent to retry. Model or connection failures have a safe, generic activity message. A retry gets a new thread ID, while earlier activity remains visible.

If the backend stops during work, restart with `npm run dev`. Startup marks interrupted runs as stopped. Claims without decisions return to waiting; saved decisions, sign-offs and payments survive. An unpaid approval offers Record payment once any required sign-off is complete. An interrupted queue run is marked stopped and keeps its recorded progress; choose Run queue again to process remaining waiting claims. There is no automatic model rerun or agent checkpoint resumption. A completed decision cannot be rerun or replaced through the API.

To start the pilot over, open Reset, type `RESET`, then choose Reset all claims. This permanently clears decisions, handler sign-offs, simulated payments, activity and batch progress, returning all claims to waiting. It retains source evidence, policies, customers/history, plans, handlers and model settings. Reset is blocked until all agents and the queue run have stopped. Opening the tab does not reset anything.

If you want to retain the entire database before resetting, stop the app and copy `undercover.sqlite3` (or the file selected by `UNDERCOVER_DB`) to a backup through your editor's file explorer.

The extension adds `GET /api/queue` for progress, `POST /api/queue/run` (HTTP 202) for a batch, and `POST /api/queue/reset` with `{"confirmation":"RESET"}`. Conflicting starts/resets return 409; missing or incorrect confirmation returns 422.

## Verification

The final `npm run check` passed on macOS with Node 26.11.1 and Python 3.12, while the development app remained running on ports 8000/5173:

- Ruff formatting/lint and pyright: pass, zero type errors.
- Pytest: 36 tests pass, 99.77% total Python coverage (80% required).
- Prettier, ESLint and strict TypeScript: pass.
- Vitest: 16 tests pass, 100% statement coverage (80% required).
- Playwright: 11 tests pass, including normal approval, direct over-limit payment rejection, handler sign-off, decline/referral, failure/retry, refresh persistence, keyboard focus, desktop/mobile layouts in both color modes, two full queue passes, refresh-persistent progress, finished-claim browsing and reset.

`uv sync`, `npm install` and `npm run dev` were also verified. The development browser loaded all 25 waiting claims and the health endpoint returned `{"status":"ok"}`. Scripts use uv commands and Node scripts compatible with Windows; a Windows machine was not available for execution.

Run individual groups with `npm run check:python`, `npm run check:ts` or `npm run e2e`. Browser tests start dedicated servers on ports 8010/5174, use an automatically removed temporary database and never reuse a development server. They use the real agent tool loop with a scripted model; unit tests also use stubs. Queue/reset scenarios use only temporary databases; the development queue was neither executed nor reset for this build. No test calls OpenRouter or reads evaluation answers. Live-model accuracy against handler decisions has not been measured.

Playwright MCP was unavailable in this session, so visual review used the installed Playwright browser. Desktop/light and mobile/dark screenshots were inspected; browser tests additionally cover both modes at 390px and 1440px, with no page errors or horizontal overflow. Restart tests verify full persistence of decisions, activity, sign-offs and payments.

No thresholds or rules were weakened, no hooks were skipped, no changes were pushed and no AWS resources were created. The student's pre-existing `package-lock.json` change was preserved byte for byte and excluded from the pilot commits.
