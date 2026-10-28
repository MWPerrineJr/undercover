# Harness plan

## Goal and scope

Turn the pilot's code-driven queue into an agent that organizes its own work, as `docs/HARNESS.md` asks. One run works every waiting claim up to a cap, the agent plans that work as a to-do list the team can watch, each claim is worked by a fresh subagent, the agent looks up the sections of the policy wording and the claims manual it needs instead of being handed whole documents, and failures are put right without stopping the run or stranding a claim.

Build on the existing pilot: FastAPI and SQLite in `backend/`, LangChain `create_agent` on OpenRouter in `agent/`, React/Vite in `dashboard/`, Playwright in `e2e/`. No second agent framework. The rules in `docs/SPEC.md` stay, including sign-off above $1,000. Tests never call a model. `data/evals/` is never opened, and no instruction or test is written from it.

## Starting point

The pilot is on branch `week1day3-mwp` ("completed pilot project"); `main` currently holds the hello-world skeleton plus the lab notebooks and `docs/HARNESS.md`. Before Phase 1, bring the pilot onto `main`:

- [x] Commit any outstanding notebook work, then `git merge week1day3-mwp` into `main`, keeping `main`'s `labs/`, `MyWork/` and lock files where they conflict.
- [x] `docs/PLAN.md` (the pilot's finished plan) and `docs/QUEUE.md` arrive with the merge and stay as they are until Phase 6.
- [x] `npm run check` is green on `main` before any harness work starts.

## Design decisions

- **The agent organizes, the backend records.** `backend/queue.py` stops being the loop. It owns a run record, the to-do list, the cap and the state transitions; the queue agent decides the order and what to do next. Code enforces the invariants the business cares about (cap, one decision, one payment, sign-off above $1,000); the model decides nothing that is enforceable.
- **Two agents, two instruction texts.** A queue agent that plans and delegates, and a claim agent that works one claim. Both prompts live in `backend/instructions.py`, served read only, written from the wording and the manual alone.
- **A subagent is a fresh `create_agent` per claim.** The queue agent's `work_claim` tool calls the claim agent with a new thread id and a new message list, and gets back one line. Nothing from claim A is in claim B's context, so per-claim cost stays flat across the run.
- **Documents are looked up, not handed over.** Both `data/policy_wording.md` (12 numbered sections) and `data/claims_manual.md` (14 numbered sections) are split on `## N. Title` at seed time. The agent gets a contents list, a search and a read-one-section tool; `read_wording` goes away. The dashboard keeps whole-document endpoints for display.
- **Reads are recorded as activity.** `activity` gains a required `kind` of `step` or `read`, so the claim page can show what the agent read without parsing messages.
- **Failure is a value, not an exception.** `work_claim` always returns a line. A claim that fails before a decision goes back to `waiting` with `attempts` incremented; the second failure moves it to `left_for_handler`. Decisions and payments stay single through the pilot's existing transactional guards.
- **The cap is a budget held by the backend.** The waiting-claims tool reports the remaining budget, and a `work_claim` beyond the cap is refused with `409`. `finish_run` is refused while budget remains and waiting claims are untried, so the missed-claim check cannot be skipped.
- **No new services.** Runs still execute as FastAPI background tasks against the same SQLite file, with the same startup recovery.

## Phase 1: Looking up the wording and the manual

Give the agent a handler's way into the documents before anything else depends on it.

Backend: seed `data/claims_manual.md` alongside the wording; add `sections(text)` to `backend/store.py`; add `backend/documents.py` with `GET /api/documents` (`list_documents`), `GET /api/documents/{document}/sections/{number}` (`read_section`) and `GET /api/documents/search` with a required `q` (`search_documents`). Add the `kind` column to `activity` and the field to `Activity`.

Agent: replace `read_wording` with `list_documents`, `search_documents` and `read_section`; record each read as `kind="read"` with the document and section title. Add `manual_sections` to `Decision` (a list that may be empty) beside `policy_sections`. Rewrite the claim instructions to look sections up and to cite both.

Success criteria:

- [x] `GET /api/documents` lists `policy_wording` with 12 sections and `claims_manual` with 14, and every number and title matches the `## N.` headings in `data/`.
- [x] `GET /api/documents/claims_manual/sections/9` returns section 9, "Repeat claims", and nothing from sections 8 or 10; section 99 returns `404`.
- [x] `GET /api/documents/search?q=wild%20animal` returns manual section 7, and `?q=meals` returns manual section 10.
- [x] Seed tests still prove only the allowlisted files are opened, now including `claims_manual.md` and still excluding `data/evals/` and `data/security/`.
- [x] A stub-model claim run records `read` activity rows naming the sections, and the agent's tool list no longer contains `read_wording`.
- [x] A decision citing manual section 9 and wording section 5 round-trips through `POST /api/claims/{id}/decision` and back out of `GET /api/claims/{id}`.
- [x] `docs/SPEC.md` no longer lists the claims manual under "Not for now" and says the agent looks it up section by section.
- [x] `npm run check:python` is green.

## Phase 2: A fresh claim agent for each claim

Split the claim work out so it can be delegated, and make it report in one line.

Add `agent/claim.py` with `work_claim(claim_id, thread_id, llm=None) -> str`, holding the per-claim tools. `agent/main.py` keeps `run(claim_id, thread_id, llm=None)` as the single-claim entry point and delegates, so `backend/runs.py`, the browser-test server and the existing tests keep working. Each call builds its own agent, model client and message list.

Report lines: `CLM-1002 approve $1,250.00 waiting for sign-off`, `CLM-1003 decline $0.00`, `CLM-1004 refer $0.00`, `CLM-1005 failed: no decision saved`.

Success criteria:

- [x] Unit tests with the scripted stub assert each of the four report lines, including the payment and sign-off wording.
- [x] A test running two claims in one process asserts different thread ids and that the second agent's message history contains nothing from the first claim.
- [x] Activity for each claim stays on that claim; `GET /api/claims/{id}/activity` for the second claim contains no events from the first.
- [x] `POST /api/claims/{id}/run` and the existing single-claim e2e test behave exactly as before.
- [x] `npm run check:python` and `npm run e2e` are green.

## Phase 3: One run, a to-do list and a cap

Hand the organizing to a queue agent.

Backend: `runs` table (id, cap, status, summary, timestamps) and `todos` table (run_id, position, claim_id, title, state in `to_do`/`in_progress`/`done`/`left_for_handler`, note). Rewrite `backend/queue.py` around it: `POST /api/queue/run` taking a cap starts a background queue agent and returns `202`; `GET /api/queue` returns the current run with its to-do list and summary; `GET /api/queue/waiting` returns waiting claims with the remaining budget; `POST /api/queue/{run_id}/todos` sets the list; `POST /api/queue/{run_id}/todos/{claim_id}` updates one item; `POST /api/queue/{run_id}/finish` records the summary. `POST /api/queue/reset` stays.

Agent: `agent/queue.py` with `run_queue(run_id, llm=None)` and tools `list_waiting_claims`, `set_todo_list`, `update_todo`, `work_claim`, `finish_run`. The agent chooses the order. Add `agent/__main__.py` so `uv run -m agent --cap 5` starts a capped run and `uv run -m agent --claim CLM-1001` runs one named claim against the running backend.

Instructions: `backend/instructions.py` gains `QUEUE_INSTRUCTIONS`; `GET /api/instructions` returns both texts as a list of `{name, title, text}`, and the dashboard's instructions panel renders both. The queue page's cap input and to-do list were built here rather than in Phase 5, so the queue UI was written once.

Success criteria:

- [x] A stub-model test on a fresh temporary database with a cap of 3 decides exactly 3 claims and leaves 22 waiting; `GET /api/queue` shows 3 to-do items `done`, the run `finished` and a non-empty summary.
- [x] A to-do item is `in_progress` while its claim is being worked: a stub that records state at each update shows `to_do` -> `in_progress` -> `done`.
- [x] `work_claim` on a claim beyond the cap returns `409` and the run still finishes cleanly.
- [x] The run order comes from the agent: a stub that picks the two largest claims works exactly those two.
- [x] `uv run -m agent --cap 2` and `uv run -m agent --claim CLM-1001` are covered by tests with a stub model, and both exit non-zero when the backend is unreachable.
- [x] `GET /api/instructions` returns the queue and claim texts, and neither mentions anything from `data/evals/`.
- [x] `npm run check:python` and `npm run check:ts` are green.

## Phase 4: Problems put right automatically

Make a long run survive its own weather.

Add `attempts` to `claims`. A run that fails before a decision returns the claim to `waiting` and increments `attempts`; at two attempts the claim is left for a handler, with activity saying so and its to-do item in `left_for_handler`. "Left for a handler" is derived from `attempts` rather than stored as a fifth claim status, so no existing database needs its `CHECK` constraint rebuilt; the backend refuses to start such a claim again and the queue and claim pages badge it. The cap counts the distinct claims a run takes, so a retry of the same claim does not spend another slot. Give the model client an explicit timeout and retry count, and keep the httpx timeout. `work_claim` catches everything and returns a failure line. `finish_run` is refused with `409` while budget remains and waiting, untried claims exist, and the accepted summary records how many claims were checked and how many were left for a handler.

Success criteria:

- [x] A stub whose second claim raises still works the remaining claims; the run finishes and its summary names the failure.
- [x] A claim that fails before a decision is back at `waiting` with `attempts` 1, and a later attempt in the same run decides it.
- [x] A claim that fails twice ends at `left_for_handler` with its to-do item `left_for_handler`, and is not tried a third time.
- [x] A claim already decided is skipped: `work_claim` returns "already decided" and no second decision or payment row is written.
- [x] A direct second `POST .../decision` and a second `POST .../payment` still return `409`, and payment above $1,000 without sign-off still returns `409`.
- [x] `finish_run` with waiting claims inside the cap returns `409`; after those claims are worked it succeeds and the summary counts them.
- [x] A model timeout is surfaced as a failure line, not a traceback, and the claim returns to `waiting`.
- [x] `npm run check:python` is green.

## Phase 5: What the team sees

Show the plan and the lookups.

Queue page: a cap input beside Run queue, and a to-do list panel for the current run with state chips, the current item highlighted and the summary when the run finishes, refreshing live as it does today. Claim page: a "What the agent read" list built from `read` activity, showing document and section titles, and decision citations for both wording and manual sections. Instructions page: both texts with headings. `format.ts` gets a label and badge for "left for a handler".

Success criteria:

- [ ] Vitest covers the to-do list panel (all four states), the cap input and the read list; `npm run check:ts` is green with coverage above 80%.
- [ ] An e2e test starts a capped run from the dashboard and sees the to-do list fill in, items tick off and the summary appear, with the uncapped claims still in the queue.
- [ ] An e2e test opens a decided claim and sees the sections the agent read and the cited wording and manual sections.
- [ ] The instructions page shows both the queue and claim instructions, read only.
- [ ] Playwright MCP: the queue and claim pages at 390px and 1440px, in light and dark, with no horizontal overflow and no console errors.
- [ ] `npm run check` is green.

## Phase 6: The model, the documents and a live run

- [ ] `DEFAULT_MODEL` becomes `deepseek/deepseek-v4.1-flash` with low reasoning effort; `MODEL_NAME` still overrides it and still omits the reasoning setting when it does.
- [ ] Reset from the dashboard, then one live run capped at 5 on the default model works 5 claims on its own, with the other 20 left waiting.
- [ ] During that run the dashboard shows the to-do list filling in and being ticked off, and each claim's steps including the sections read.
- [ ] No claim is decided or paid twice, and any approval over $1,000 is still waiting for sign-off.
- [ ] `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the product as it now is; `docs/QUEUE.md` is folded into `docs/STATUS.md` and removed.
- [ ] `npm run check` is green and its results are reported.

## Rules this plan keeps

- Every criterion above is ticked off in this file as it is met, and `docs/STATUS.md` is updated each phase.
- Tests never call a model; stubs live in `agent/tests/stubs.py` and `backend/tests/server.py`.
- No threshold lowered, no rule disabled, no file excluded, no `--no-verify`, no push.
- `data/evals/` stays closed.
