from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event

import pytest
from fastapi.testclient import TestClient

from backend import runs, store, workflow
from backend.main import app
from backend.models import Decision, Payment, SignOff


def test_background_activity_and_duplicates(client, monkeypatch):
    entered, release = Event(), Event()

    def delayed(claim_id, thread_id):
        entered.set()
        release.wait(5)

    monkeypatch.setattr(runs, "run_agent", delayed)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(client.post, "/api/claims/CLM-1001/run")
        assert entered.wait(5)
        claim = client.get("/api/claims/CLM-1001").json()
        assert claim["status"] == "in_progress"
        assert claim["running"]
        assert client.post("/api/claims/CLM-1001/run").status_code == 409
        assert (
            client.post(
                "/api/claims/CLM-1001/activity",
                json={
                    "thread_id": claim["thread_id"],
                    "message": "Reading evidence",
                    "kind": "step",
                },
            ).status_code
            == 200
        )
        assert (
            client.get("/api/claims/CLM-1001/activity").json()[-1]["message"]
            == "Reading evidence"
        )
        release.set()
        assert future.result().status_code == 202
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"
    assert (
        client.post(
            "/api/claims/CLM-1001/activity",
            json={
                "thread_id": claim["thread_id"],
                "message": "Too late",
                "kind": "step",
            },
        ).status_code
        == 409
    )


@pytest.mark.parametrize("saved", [False, True])
def test_failure_and_recovery(client, monkeypatch, saved):
    thread = workflow.start("CLM-1001")["thread_id"]
    if saved:
        workflow.decide(
            "CLM-1001",
            Decision(
                thread_id=thread,
                outcome="approve",
                payout=Decimal("100"),
                calculation="100",
                explanation="Synthetic test. See section 3.",
                policy_sections=[3],
                manual_sections=[],
            ),
        )

    def failing(*args):
        raise RuntimeError("Do not expose this secret")

    monkeypatch.setattr(runs, "run_agent", failing)
    runs.execute("CLM-1001", thread)
    claim = client.get("/api/claims/CLM-1001").json()
    assert not claim["running"]
    assert bool(claim["decision"]) == saved
    assert claim["status"] == ("in_progress" if saved else "waiting")
    assert "secret" not in str(client.get("/api/claims/CLM-1001/activity").json())
    with store.connect() as db:
        db.execute("UPDATE claims SET running=1 WHERE id='CLM-1001'")
    runs.recover()
    assert not client.get("/api/claims/CLM-1001").json()["running"]
    if saved:
        assert client.post("/api/claims/CLM-1001/run").status_code == 409
    else:
        workflow.start("CLM-1001")


def test_concurrent_start(client):
    def attempt(_):
        try:
            return workflow.start("CLM-1001")
        except workflow.ConflictError:
            return "conflict"

    with ThreadPoolExecutor() as pool:
        results = list(pool.map(attempt, range(2)))
    assert results.count("conflict") == 1


def test_success_completion(client, monkeypatch):
    def approve(claim_id, thread_id):
        workflow.decide(
            claim_id,
            Decision(
                thread_id=thread_id,
                outcome="refer",
                payout=Decimal("0"),
                calculation="No payment",
                explanation="Needs evidence. See section 11.",
                policy_sections=[11],
                manual_sections=[],
            ),
        )

    monkeypatch.setattr(runs, "run_agent", approve)
    assert client.post("/api/claims/CLM-1001/run").status_code == 202
    assert (
        client.get("/api/claims/CLM-1001/activity").json()[-1]["message"]
        == "Run finished"
    )
    assert client.post("/api/claims/CLM-1001/run").status_code == 409


def test_restart_preserves_sign_off_payment_and_activity(client):
    thread = workflow.start("CLM-1001")["thread_id"]
    workflow.decide(
        "CLM-1001",
        Decision(
            thread_id=thread,
            outcome="approve",
            payout=Decimal("1250"),
            calculation="1250",
            explanation="Covered. See section 3.",
            policy_sections=[3],
            manual_sections=[],
        ),
    )
    runs.recover()
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting_for_sign_off"
    workflow.sign_off("CLM-1001", SignOff(thread_id=thread, handler_id="HND-01"))
    workflow.pay("CLM-1001", Payment(thread_id=thread, amount=Decimal("1250")))
    before = client.get("/api/claims/CLM-1001").json()
    events = client.get("/api/claims/CLM-1001/activity").json()
    with TestClient(app) as restarted:
        assert restarted.get("/api/claims/CLM-1001").json() == before
        assert restarted.get("/api/claims/CLM-1001/activity").json() == events
