"""The claims API shared by the dashboard and agent."""

import json

from fastapi import APIRouter

from backend import store, workflow
from backend.instructions import TEXTS
from backend.models import Activity, Decision, Payment, SignOff

router = APIRouter(prefix="/api")


@router.get("/claims", operation_id="list_claims")
def list_claims() -> list[dict]:
    """List the queue with workflow, decision and payment states."""
    with store.connect() as db:
        claims = [
            store.claim_record(db, row["id"])
            for row in db.execute("SELECT id FROM claims ORDER BY id")
        ]
        return [
            {
                "claim_id": c["claim_id"],
                "customer_name": store.record(db, "customers", c["customer_id"])[
                    "name"
                ],
                "claim_type": c["claim_type"],
                "summary": c["summary"],
                "amount_claimed": c["amount_claimed"],
                "status": c["status"],
                "running": c["running"],
                "attempts": c["attempts"],
                "left_for_handler": c["left_for_handler"],
                "decision": c["decision"],
                "payment": c["payment"],
            }
            for c in claims
        ]


@router.get("/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> dict:
    """Read the full claim and its persisted workflow."""
    with store.connect() as db:
        return store.claim_record(db, claim_id)


@router.get("/claims/{claim_id}/policy", operation_id="get_claim_policy")
def get_claim_policy(claim_id: str) -> dict:
    """Read the policy and trip behind the claim."""
    with store.connect() as db:
        return store.record(
            db, "policies", store.claim_record(db, claim_id)["policy_id"]
        )


@router.get("/claims/{claim_id}/customer", operation_id="get_claim_customer")
def get_claim_customer(claim_id: str) -> dict:
    """Read the customer behind the claim, including earlier claims."""
    with store.connect() as db:
        return store.record(
            db, "customers", store.claim_record(db, claim_id)["customer_id"]
        )


@router.get("/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str) -> dict:
    """Read the customer's policy and trip."""
    with store.connect() as db:
        return store.record(db, "policies", policy_id)


@router.get("/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str) -> dict:
    """Read the customer including earlier claims."""
    with store.connect() as db:
        return store.record(db, "customers", customer_id)


@router.get("/plans", operation_id="get_plans")
def get_plans() -> dict:
    """Read plan limits, waiting periods, deductibles and add-ons."""
    with store.connect() as db:
        return store.record(db, "plans", "plans")


@router.get("/policy-wording", operation_id="get_wording")
def get_wording() -> dict:
    """Read the policy wording and its version."""
    with store.connect() as db:
        return store.record(db, "wording", "wording")


@router.get("/instructions", operation_id="list_instructions")
def list_instructions() -> list[dict]:
    """Read every set of instructions the UnderCover Agent works to."""
    return [{"name": name, **text} for name, text in TEXTS.items()]


@router.get("/instructions/{name}", operation_id="get_instructions")
def get_instructions(name: str) -> dict:
    """Read one named set of the agent's instructions."""
    if name not in TEXTS:
        raise LookupError("Instructions not found")
    return {"name": name, **TEXTS[name]}


@router.get("/handlers", operation_id="list_handlers")
def list_handlers() -> list[dict]:
    """List the claims handlers who can sign off payments."""
    with store.connect() as db:
        return [
            json.loads(row["body"])
            for row in db.execute(
                "SELECT body FROM records WHERE kind='handlers' ORDER BY id"
            )
        ]


@router.get("/claims/{claim_id}/activity", operation_id="get_activity")
def get_activity(claim_id: str) -> list[dict]:
    """Read ordered operational events for a claim."""
    with store.connect() as db:
        store.claim_record(db, claim_id)
        return [
            dict(row)
            for row in db.execute(
                "SELECT * FROM activity WHERE claim_id=? ORDER BY id", (claim_id,)
            )
        ]


@router.post("/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, request: Decision) -> dict:
    """Record the active run's structured claim decision."""
    return workflow.decide(claim_id, request)


@router.post("/claims/{claim_id}/sign-off", operation_id="sign_off")
def sign_off(claim_id: str, request: SignOff) -> dict:
    """Record a handler's sign-off against the approved decision."""
    return workflow.sign_off(claim_id, request)


@router.post("/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, request: Payment) -> dict:
    """Record a simulated payment after checking the approval boundary."""
    return workflow.pay(claim_id, request)


@router.post("/claims/{claim_id}/activity", operation_id="record_activity")
def record_activity(claim_id: str, request: Activity) -> dict:
    """Record a concise operational event for the active run."""
    with store.connect() as db:
        claim = workflow.current(db, claim_id, request.thread_id)
        if not claim["running"]:
            raise workflow.ConflictError("This run has finished")
        store.event(db, claim_id, request.thread_id, request.message, request.kind)
    return {"recorded": True}
