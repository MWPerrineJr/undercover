# Tech stack

- `backend/`: FastAPI and SQLite. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount.
- `agent/`: LangChain's `create_agent` on OpenRouter, in two agents. The queue agent (`agent/queue.py`) plans a run and delegates; the claim agent (`agent/claim.py`) works one claim from a clean start and reports in a line. `agent/main.py` keeps the entry point that takes a claim id and a thread id, `agent/tools.py` holds the per-claim tools, `agent/api.py` the backend client and `agent/model.py` the model. `uv run -m agent --cap 5` or `--claim CLM-1001` starts a run from the command line. Both agents reach claims, documents and their instructions only through the backend's API. The default model is `deepseek/deepseek-v4.1-flash` with low reasoning effort, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`.
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- `data/`: the business data the backend starts from, including the policy wording and the claims manual. Both are served section by section, so the agent looks up what it needs instead of being handed whole documents. The agent never sees `data/evals/`, which holds the answer key.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
