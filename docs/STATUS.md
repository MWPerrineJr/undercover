# Status

Pilot phases 1–3 are complete. The SQLite claims API enforces separate decisions, handler sign-offs and exact simulated payments. The UnderCover Agent uses LangChain `create_agent`, obtains instructions and all business records through HTTP tools, records operational tool activity and respects `MODEL_NAME`. Runs execute in background tasks with duplicate-start protection and restart recovery. The dashboard is next.

Run `uv sync` and `npm install` at the root, then `npm run dev`. Backend: http://localhost:8000; API reference: http://localhost:8000/docs; dashboard: http://localhost:5173. Database: `undercover.sqlite3` (ignored), overridden by `UNDERCOVER_DB`. Set `OPENROUTER_API_KEY` in `.env`; default model is `openai/gpt-6-luna` with low reasoning effort; `MODEL_NAME` overrides it. `BACKEND_URL` defaults to http://localhost:8000.

`POST /api/claims/{claim_id}/run` returns a thread ID with HTTP 202. Poll claim/activity endpoints for progress. An interrupted or failed run without a decision returns to waiting for an explicit retry. Saved decisions and payments survive failures/restarts; an unpaid approval can be paid using its exact stored amount after any required sign-off. There is no automatic model rerun, durable agent checkpoint or real payment.

Verification: `npm run check:python` passes 27 tests at 99.71% coverage, including all tool sequences, failures, concurrency and interruption recovery. A separate HTTP probe against the isolated scripted server returned 202 in 11 ms and exposed activity while work continued. Tests never call OpenRouter, and no evaluation records were opened.
