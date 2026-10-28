"""The queue run: the agent plans it, the backend records and bounds it."""

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks

from agent.queue import run_queue as run_queue_agent
from backend import runs, store, workflow
from backend.models import (
    ClaimReport,
    ResetQueue,
    RunSummary,
    StartRun,
    TodoList,
    TodoUpdate,
)

router = APIRouter(prefix="/api/queue")
IDLE = {
    "run_id": None,
    "cap": 0,
    "worked": 0,
    "status": "idle",
    "summary": None,
    "started_at": None,
    "finished_at": None,
    "todos": [],
}


def latest(db) -> dict:
    """Read the most recent run with its to-do list."""
    row = db.execute(
        "SELECT * FROM runs ORDER BY started_at DESC, rowid DESC"
    ).fetchone()
    if row is None:
        return dict(IDLE)
    todos = db.execute(
        "SELECT claim_id, title, state, note FROM todos WHERE run_id=? "
        "ORDER BY position",
        (row["id"],),
    )
    return {
        "run_id": row["id"],
        "cap": row["cap"],
        "worked": row["worked"],
        "status": row["status"],
        "summary": row["summary"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "todos": [dict(todo) for todo in todos],
    }


def active(db, run_id: str) -> dict:
    """Lock and read a run that is still going."""
    db.execute("BEGIN IMMEDIATE")
    row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise LookupError("Run not found")
    if row["status"] != "running":
        raise workflow.ConflictError("This run has finished")
    return dict(row)


def waiting_claims(db) -> list[dict]:
    """List the claims still waiting for a decision."""
    rows = db.execute(
        "SELECT id FROM claims WHERE status='waiting' AND decision IS NULL "
        "AND running=0 ORDER BY id"
    ).fetchall()
    claims = [store.claim_record(db, row["id"]) for row in rows]
    return [
        {
            field: claim[field]
            for field in (
                "claim_id",
                "claim_type",
                "summary",
                "submitted_on",
                "amount_claimed",
            )
        }
        for claim in claims
    ]


def execute(run_id: str):
    """Run the queue agent away from the request and leave the run closed."""
    try:
        run_queue_agent(run_id)
        ending = "Run ended without a summary"
    except Exception:
        ending = "Run stopped: check the backend and model configuration"
    with store.connect() as db:
        db.execute(
            "UPDATE runs SET status='stopped', summary=?, "
            "finished_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
            "WHERE id=? AND status='running'",
            (ending, run_id),
        )


def recover():
    """Mark an interrupted run stopped without restarting model calls."""
    with store.connect() as db:
        db.execute(
            "UPDATE runs SET status='stopped', summary=?, "
            "finished_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE status='running'",
            ("Queue run interrupted by a restart; start another run to continue",),
        )
        db.execute("UPDATE todos SET state='to_do' WHERE state='in_progress'")


@router.get("", operation_id="get_queue_run")
def get_queue_run() -> dict:
    """Read the current or most recent run with its to-do list."""
    with store.connect() as db:
        return latest(db)


@router.post("/run", status_code=202, operation_id="run_queue")
def run_queue(request: StartRun, background_tasks: BackgroundTasks) -> dict:
    """Start one agent-organized run over the waiting claims."""
    run_id = str(uuid4())
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if latest(db)["status"] == "running":
            raise workflow.ConflictError("A queue run is already active")
        if not waiting_claims(db):
            raise workflow.ConflictError("No waiting claims to run")
        db.execute("INSERT INTO runs (id, cap) VALUES (?, ?)", (run_id, request.cap))
        progress = latest(db)
    background_tasks.add_task(execute, run_id)
    return progress


@router.get("/{run_id}/waiting", operation_id="list_waiting_claims")
def list_waiting(run_id: str) -> dict:
    """List the waiting claims and how many this run may still work."""
    with store.connect() as db:
        run = active(db, run_id)
        return {
            "remaining": run["cap"] - run["worked"],
            "claims": waiting_claims(db),
        }


@router.post("/{run_id}/todos", operation_id="set_todo_list")
def set_todo_list(run_id: str, request: TodoList) -> dict:
    """Replace the run's to-do list with the agent's plan."""
    with store.connect() as db:
        active(db, run_id)
        for item in request.items:
            store.claim_record(db, item.claim_id)
        db.execute("DELETE FROM todos WHERE run_id=?", (run_id,))
        db.executemany(
            "INSERT INTO todos (run_id, claim_id, position, title) VALUES (?, ?, ?, ?)",
            [
                (run_id, item.claim_id, position, item.title)
                for position, item in enumerate(request.items)
            ],
        )
        return latest(db)


@router.post("/{run_id}/todos/{claim_id}", operation_id="update_todo")
def update_todo(run_id: str, claim_id: str, request: TodoUpdate) -> dict:
    """Move one to-do item on and record what happened."""
    with store.connect() as db:
        active(db, run_id)
        changed = db.execute(
            "UPDATE todos SET state=?, note=? WHERE run_id=? AND claim_id=?",
            (request.state, request.note, run_id, claim_id),
        ).rowcount
        if not changed:
            raise LookupError("To-do item not found")
        return latest(db)


@router.post("/{run_id}/claims/{claim_id}/start", operation_id="start_queue_claim")
def start_queue_claim(run_id: str, claim_id: str) -> dict:
    """Take one claim for this run, inside its cap."""
    with store.connect() as db:
        run = active(db, run_id)
        if run["worked"] >= run["cap"]:
            raise workflow.ConflictError("This run has reached its cap")
        thread_id = workflow.reserve(db, claim_id)
        db.execute("UPDATE runs SET worked=worked+1 WHERE id=?", (run_id,))
        return {"thread_id": thread_id}


@router.post("/{run_id}/claims/{claim_id}/finish", operation_id="finish_queue_claim")
def finish_queue_claim(run_id: str, claim_id: str, request: ClaimReport) -> dict:
    """Release one claim and record what the claim agent reported."""
    with store.connect() as db:
        active(db, run_id)
    runs.finish(claim_id, request.thread_id, f"Run finished: {request.report}")
    with store.connect() as db:
        return store.claim_record(db, claim_id)


@router.post("/{run_id}/finish", operation_id="finish_run")
def finish_run(run_id: str, request: RunSummary) -> dict:
    """Close the run with a summary for the handlers."""
    with store.connect() as db:
        active(db, run_id)
        db.execute(
            "UPDATE runs SET status='finished', summary=?, "
            "finished_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
            (request.summary, run_id),
        )
        return latest(db)


@router.post("/reset", operation_id="reset_queue")
def reset_queue(request: ResetQueue) -> dict:
    """Clear claim workflow and run history when no agent is working."""
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        working = db.execute("SELECT id FROM claims WHERE running=1 LIMIT 1").fetchone()
        if latest(db)["status"] == "running" or working:
            raise workflow.ConflictError(
                "Wait for all agent runs to finish before resetting"
            )
        db.execute("DELETE FROM activity")
        db.execute("DELETE FROM todos")
        db.execute("DELETE FROM runs")
        db.execute(
            "UPDATE claims SET status='waiting', running=0, thread_id=NULL, "
            "decision=NULL, sign_off=NULL, payment=NULL"
        )
        total = db.execute("SELECT count(*) FROM claims").fetchone()[0]
    return {"reset_claims": total}
