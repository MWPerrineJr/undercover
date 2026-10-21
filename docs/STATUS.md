# Status

Pilot phase 1 is complete: SQLite seeds the 25 queue claims and associated business records, retains their full source fields and preserves changes on restart. Only the six named JSON files and policy wording are loaded. The API, agent and dashboard are still the health-check skeleton.

Run `uv sync` and `npm install` at the root, then `npm run dev`. The backend is at http://localhost:8000 and the dashboard at http://localhost:5173. The local database is `undercover.sqlite3` (ignored by git); `UNDERCOVER_DB` overrides its path.

Phase 1 verification: Python format, lint, types and tests pass, with coverage above 80%. Storage tests use temporary databases and verify source fidelity, relationships, the seed-file allowlist and restart preservation. No evaluation records were opened.
