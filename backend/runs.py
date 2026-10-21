"""In-process agent runs with persisted operational activity."""

from fastapi import APIRouter, BackgroundTasks

from agent.main import run as run_agent
from backend import store, workflow

router = APIRouter(prefix="/api")


def finish(claim_id: str, thread_id: str, message: str):
    """Release a run without discarding any saved decision or payment."""
    with store.connect() as db:
        claim = workflow.current(db, claim_id, thread_id)
        status = claim["status"] if claim["decision"] else "waiting"
        db.execute(
            "UPDATE claims SET running=0, status=? WHERE id=?", (status, claim_id)
        )
        store.event(db, claim_id, thread_id, message)


def execute(claim_id: str, thread_id: str):
    """Run the model away from the request and record a safe completion status."""
    try:
        run_agent(claim_id, thread_id)
        with store.connect() as db:
            claim = store.claim_record(db, claim_id)
        message = (
            "Run finished"
            if claim["decision"]
            else "Run failed: no decision saved; retry available"
        )
    except Exception:
        message = (
            "Run failed: check backend and model configuration; retry unfinished work"
        )
    finish(claim_id, thread_id, message)


def recover():
    """Release interrupted runs on startup without making model calls."""
    with store.connect() as db:
        rows = db.execute(
            "SELECT id, thread_id, decision, status FROM claims WHERE running=1"
        ).fetchall()
        for row in rows:
            status = row["status"] if row["decision"] else "waiting"
            db.execute(
                "UPDATE claims SET running=0, status=? WHERE id=?", (status, row["id"])
            )
            store.event(
                db,
                row["id"],
                row["thread_id"],
                "Run interrupted by restart; saved work preserved",
            )


@router.post("/claims/{claim_id}/run", status_code=202, operation_id="start_run")
def start_run(claim_id: str, background_tasks: BackgroundTasks) -> dict:
    """Start a background agent run on a waiting claim."""
    result = workflow.start(claim_id)
    background_tasks.add_task(execute, claim_id, result["thread_id"])
    return result
