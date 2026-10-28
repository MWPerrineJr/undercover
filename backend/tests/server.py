"""Isolated browser-test server using the real agent loop with a scripted model."""

import os
import time
from tempfile import TemporaryDirectory

import uvicorn

from agent.main import run
from agent.queue import run_queue
from agent.tests.stubs import queue_script, scripted
from backend import queue, runs, store
from backend.main import app

ATTEMPTS: dict[str, int] = {}


def scripted_run(claim_id: str, thread_id: str):
    """Use synthetic outcomes unrelated to the evaluation answer key."""
    time.sleep(0.4)
    ATTEMPTS[claim_id] = ATTEMPTS.get(claim_id, 0) + 1
    if claim_id in {"CLM-1005", "CLM-1025"} and ATTEMPTS[claim_id] == 1:
        raise ConnectionError("Synthetic unavailable model")
    outcome, amount = {
        "CLM-1002": ("approve", "1250.00"),
        "CLM-1003": ("decline", "0"),
        "CLM-1004": ("refer", "0"),
    }.get(claim_id, ("approve", "420.00"))
    return run(claim_id, thread_id, scripted(outcome, amount, outcome == "approve"))


def scripted_queue(run_id: str):
    """Plan and work the run with scripted models instead of a remote one."""
    with store.connect() as db:
        cap = db.execute("SELECT cap FROM runs WHERE id=?", (run_id,)).fetchone()["cap"]
        claim_ids = [claim["claim_id"] for claim in queue.waiting_claims(db)][:cap]
    return run_queue(run_id, queue_script(claim_ids), scripted_run)


def main():
    """Serve an ephemeral database on the dedicated browser-test port."""
    with TemporaryDirectory(prefix="undercover-e2e-") as directory:
        os.environ["UNDERCOVER_DB"] = f"{directory}/test.sqlite3"
        os.environ["BACKEND_URL"] = "http://127.0.0.1:8010"
        runs.run_agent = scripted_run
        queue.run_queue_agent = scripted_queue
        uvicorn.run(app, host="127.0.0.1", port=8010)


if __name__ == "__main__":
    main()
