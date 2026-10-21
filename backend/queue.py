"""A single sequential run of the waiting claims queue."""

from typing import Literal

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from backend import runs, store, workflow

router = APIRouter(prefix="/api/queue")


class QueueRun(BaseModel):
    running: bool = False
    total: int = 0
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    current_claim_id: str | None = None
    message: str = "Ready to run waiting claims"
    claim_ids: list[str] = Field(default_factory=list)


def read(db) -> QueueRun:
    """Read the latest queue progress, including its private snapshot."""
    row = db.execute(
        "SELECT body FROM records WHERE kind='queue' AND id='latest'"
    ).fetchone()
    return QueueRun.model_validate_json(row["body"]) if row else QueueRun()


def save(db, progress: QueueRun):
    """Persist queue progress without changing any claim."""
    db.execute(
        "INSERT INTO records VALUES ('queue', 'latest', ?) "
        "ON CONFLICT(kind, id) DO UPDATE SET body=excluded.body",
        (progress.model_dump_json(),),
    )


def reserve() -> QueueRun:
    """Atomically snapshot waiting claims for one batch."""
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if read(db).running:
            raise workflow.ConflictError("A queue run is already active")
        ids = [
            row["id"]
            for row in db.execute(
                "SELECT id FROM claims WHERE status='waiting' AND decision IS NULL "
                "AND running=0 ORDER BY id"
            )
        ]
        if not ids:
            raise workflow.ConflictError("No waiting claims to run")
        progress = QueueRun(
            running=True,
            total=len(ids),
            claim_ids=ids,
            message="Reviewing waiting claims",
        )
        save(db, progress)
        return progress


def attempt(claim_id: str) -> str:
    """Attempt a snapshot claim once, skipping work already taken by a handler."""
    try:
        thread_id = workflow.start(claim_id)["thread_id"]
    except workflow.ConflictError:
        return "skipped"
    return "reviewed" if runs.execute(claim_id, thread_id) else "failed"


def execute(claim_ids: list[str]):
    """Review the snapshot sequentially and retain progress after every claim."""
    for claim_id in claim_ids:
        with store.connect() as db:
            progress = read(db)
            progress.current_claim_id = claim_id
            save(db, progress)
        outcome = attempt(claim_id)
        with store.connect() as db:
            progress = read(db)
            progress.processed += 1
            progress.failed += int(outcome == "failed")
            progress.skipped += int(outcome == "skipped")
            progress.current_claim_id = None
            save(db, progress)
    with store.connect() as db:
        progress = read(db)
        progress.running = False
        progress.message = "Queue run complete"
        save(db, progress)


def recover():
    """Mark an interrupted queue stopped without restarting model calls."""
    with store.connect() as db:
        progress = read(db)
        if progress.running:
            progress.running = False
            progress.current_claim_id = None
            progress.message = (
                "Queue run interrupted; run remaining waiting claims to continue"
            )
            save(db, progress)


@router.get("", operation_id="get_queue_run")
def get_queue_run() -> dict:
    """Read the latest queue run's progress."""
    with store.connect() as db:
        return read(db).model_dump(exclude={"claim_ids"})


@router.post("/run", status_code=202, operation_id="run_queue")
def run_queue(background_tasks: BackgroundTasks) -> dict:
    """Start one sequential review of all currently waiting claims."""
    progress = reserve()
    background_tasks.add_task(execute, progress.claim_ids)
    return progress.model_dump(exclude={"claim_ids"})


class ResetQueue(BaseModel):
    confirmation: Literal["RESET"]


@router.post("/reset", operation_id="reset_queue")
def reset_queue(request: ResetQueue) -> dict:
    """Clear claim workflow and queue progress when no agent is working."""
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        active_claim = db.execute(
            "SELECT id FROM claims WHERE running=1 LIMIT 1"
        ).fetchone()
        if read(db).running or active_claim:
            raise workflow.ConflictError(
                "Wait for all agent runs to finish before resetting"
            )
        db.execute("DELETE FROM activity")
        db.execute(
            "UPDATE claims SET status='waiting', running=0, thread_id=NULL, "
            "decision=NULL, sign_off=NULL, payment=NULL"
        )
        db.execute("DELETE FROM records WHERE kind='queue' AND id='latest'")
        total = db.execute("SELECT count(*) FROM claims").fetchone()[0]
    return {"reset_claims": total}
