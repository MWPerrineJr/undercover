"""Transactional workflow and simulated payments."""

from decimal import Decimal
from uuid import uuid4

from backend import store
from backend.models import Decision, Payment, SignOff


class ConflictError(Exception):
    """A request conflicts with the current claim state."""


def limit(db) -> Decimal:
    """Read the company's payment approval boundary."""
    return Decimal(str(store.record(db, "company", "company")["payout_approval_limit"]))


def current(db, claim_id: str, thread_id: str) -> dict:
    """Lock and read the claim, rejecting stale runs."""
    db.execute("BEGIN IMMEDIATE")
    claim = store.claim_record(db, claim_id)
    if claim["thread_id"] != thread_id:
        raise ConflictError("This run is no longer current")
    return claim


def reserve(db, claim_id: str) -> str:
    """Take a waiting claim for one agent run inside an open transaction."""
    claim = store.claim_record(db, claim_id)
    if claim["decision"]:
        raise ConflictError("This claim has already been decided")
    if claim["status"] != "waiting" or claim["running"]:
        raise ConflictError("Only waiting claims can be started")
    thread_id = str(uuid4())
    db.execute(
        "UPDATE claims SET status='in_progress', running=1, thread_id=? WHERE id=?",
        (thread_id, claim_id),
    )
    store.event(db, claim_id, thread_id, "Agent started")
    return thread_id


def start(claim_id: str) -> dict:
    """Reserve a waiting claim for one agent run."""
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        return {"thread_id": reserve(db, claim_id)}


def decide(claim_id: str, decision: Decision) -> dict:
    """Save the active run's decision exactly once."""
    with store.connect() as db:
        claim = current(db, claim_id, decision.thread_id)
        if claim["status"] != "in_progress" or claim["decision"]:
            raise ConflictError("A decision cannot be saved in this state")
        status = "decided"
        if decision.outcome == "approve":
            status = (
                "waiting_for_sign_off" if decision.payout > limit(db) else "in_progress"
            )
        db.execute(
            "UPDATE claims SET decision=?, status=? WHERE id=?",
            (decision.model_dump_json(), status, claim_id),
        )
        store.event(
            db, claim_id, decision.thread_id, f"Decision saved: {decision.outcome}"
        )
        if status == "waiting_for_sign_off":
            store.event(
                db, claim_id, decision.thread_id, "Payment waiting for handler sign-off"
            )
        return store.claim_record(db, claim_id)


def sign_off(claim_id: str, request: SignOff) -> dict:
    """Attach a permitted handler's sign-off to the current decision."""
    with store.connect() as db:
        claim = current(db, claim_id, request.thread_id)
        handler = store.record(db, "handlers", request.handler_id)
        decision = claim["decision"]
        if (
            claim["status"] != "waiting_for_sign_off"
            or claim["sign_off"]
            or not handler["can_approve_over_limit"]
            or not decision
            or decision["outcome"] != "approve"
        ):
            raise ConflictError("This claim cannot be signed off")
        db.execute(
            "UPDATE claims SET sign_off=? WHERE id=?",
            (request.model_dump_json(), claim_id),
        )
        store.event(db, claim_id, request.thread_id, f"Signed off by {handler['name']}")
        return store.claim_record(db, claim_id)


def pay(claim_id: str, request: Payment) -> dict:
    """Enforce the approval gate before recording a single simulated payment."""
    with store.connect() as db:
        claim = current(db, claim_id, request.thread_id)
        decision = claim["decision"]
        if not decision or decision["outcome"] != "approve" or claim["payment"]:
            raise ConflictError("Payment requires an unpaid approved decision")
        if request.amount != Decimal(decision["payout"]):
            raise ConflictError("Payment must equal the approved payout")
        if request.amount > limit(db) and not claim["sign_off"]:
            raise ConflictError("Handler sign-off is required above $1,000.00")
        db.execute(
            "UPDATE claims SET payment=?, status='decided' WHERE id=?",
            (request.model_dump_json(), claim_id),
        )
        store.event(
            db,
            claim_id,
            request.thread_id,
            f"Simulated payment recorded: ${request.amount:,.2f}",
        )
        return store.claim_record(db, claim_id)
