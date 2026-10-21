# Status

Pilot phases 1–2 are complete: SQLite persists all 25 claims and linked business records; the API exposes full records, policy wording, instructions, handlers and activity. Transactional decision, sign-off and separate simulated payment operations enforce the $1,000 boundary, exact payout amounts, stale-run rejection and single payment. The agent and dashboard remain the health-check skeleton until their phases.

Run `uv sync` and `npm install` at the root, then `npm run dev`. Backend: http://localhost:8000; API reference: http://localhost:8000/docs; dashboard: http://localhost:5173. The local database is `undercover.sqlite3` (ignored); `UNDERCOVER_DB` overrides its path.

Verification: `npm run check:python` passes 18 tests with 99.23% coverage, formatting, lint and types. Tests cover allowed seed files, complete record fidelity, restart preservation, OpenAPI inputs, all decisions, invalid amounts, $1,000/$1,000.01 payouts, sign-off and concurrent payment attempts. No evaluation records were opened.
