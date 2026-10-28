from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event

import pytest

from backend import queue, runs, store, workflow
from backend.models import Decision, Payment


def scripted_review(claim_id, thread_id):
    if claim_id == "CLM-1003":
        raise ConnectionError("Synthetic failure")
    amount = Decimal("1250") if claim_id == "CLM-1002" else Decimal("100")
    workflow.decide(
        claim_id,
        Decision(
            thread_id=thread_id,
            outcome="approve",
            payout=amount,
            calculation=str(amount),
            explanation="Synthetic. See section 3.",
            policy_sections=[3],
        ),
    )
    if amount <= 1000:
        workflow.pay(claim_id, Payment(thread_id=thread_id, amount=amount))


def test_whole_queue_continues_after_failure(client, monkeypatch):
    monkeypatch.setattr(runs, "run_agent", scripted_review)
    assert client.get("/api/queue").json()["total"] == 0
    response = client.post("/api/queue/run")
    assert response.status_code == 202
    assert response.json()["total"] == 25
    assert "claim_ids" not in response.json()
    progress = client.get("/api/queue").json()
    assert progress == {
        "running": False,
        "total": 25,
        "processed": 25,
        "failed": 1,
        "skipped": 0,
        "current_claim_id": None,
        "message": "Queue run complete",
    }
    assert client.get("/api/claims/CLM-1002").json()["status"] == "waiting_for_sign_off"
    assert client.get("/api/claims/CLM-1002").json()["payment"] is None
    assert client.get("/api/claims/CLM-1003").json()["status"] == "waiting"
    claims = client.get("/api/claims").json()
    assert sum(c["payment"] is not None for c in claims) == 23
    assert (
        client.post(
            "/api/claims/CLM-1002/payment",
            json={
                "thread_id": client.get("/api/claims/CLM-1002").json()["thread_id"],
                "amount": "1250",
            },
        ).status_code
        == 409
    )
    store.initialize()
    assert client.get("/api/queue").json() == progress
    retry = queue.reserve()
    assert retry.claim_ids == ["CLM-1003"]


def test_no_eligible_claims_and_skipped_individual_start(client, monkeypatch):
    monkeypatch.setattr(runs, "run_agent", scripted_review)
    snapshot = queue.reserve()
    thread_id = workflow.start("CLM-1001")["thread_id"]
    runs.execute("CLM-1001", thread_id)
    queue.execute(snapshot.claim_ids)
    assert client.get("/api/queue").json()["skipped"] == 1
    with store.connect() as db:
        db.execute("UPDATE claims SET status='decided' WHERE id='CLM-1003'")
    assert client.post("/api/queue/run").status_code == 409


def test_queue_duplicate_requests_and_progress(client, monkeypatch):
    entered, release = Event(), Event()
    ids = []

    def delayed(claim_id, thread_id):
        ids.append(claim_id)
        if len(ids) == 1:
            entered.set()
            release.wait(5)
        scripted_review(claim_id, thread_id)

    monkeypatch.setattr(runs, "run_agent", delayed)
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(client.post, "/api/queue/run")
        assert entered.wait(5)
        progress = client.get("/api/queue").json()
        assert progress["running"]
        assert progress["processed"] == 0
        assert progress["current_claim_id"] == "CLM-1001"
        assert ids == ["CLM-1001"]
        assert client.post("/api/queue/run").status_code == 409
        release.set()
        assert pending.result().status_code == 202
    assert ids == [f"CLM-{i}" for i in range(1001, 1026)]


def test_queue_interruption_preserves_progress_and_decisions(client, monkeypatch):
    monkeypatch.setattr(runs, "run_agent", scripted_review)
    progress = queue.reserve()
    thread_id = workflow.start(progress.claim_ids[0])["thread_id"]
    runs.execute(progress.claim_ids[0], thread_id)
    with store.connect() as db:
        progress.processed = 1
        progress.current_claim_id = "CLM-1002"
        queue.save(db, progress)
    queue.recover()
    current = client.get("/api/queue").json()
    assert not current["running"]
    assert current["processed"] == 1
    assert "interrupted" in current["message"]
    assert client.get("/api/claims/CLM-1001").json()["payment"]
    assert len(queue.reserve().claim_ids) == 24


def test_atomic_queue_reservation(client):
    def start(_):
        try:
            return queue.reserve().total
        except workflow.ConflictError:
            return "conflict"

    with ThreadPoolExecutor() as pool:
        results = list(pool.map(start, range(2)))
    assert sorted(str(r) for r in results) == ["25", "conflict"]


def test_reset_requires_confirmation_and_preserves_business_records(
    client, monkeypatch
):
    monkeypatch.setattr(runs, "run_agent", scripted_review)
    client.post("/api/queue/run")
    source = client.get("/api/claims/CLM-1001").json()
    policy = client.get(f"/api/policies/{source['policy_id']}").json()
    assert client.post("/api/queue/reset", json={}).status_code == 422
    assert (
        client.post("/api/queue/reset", json={"confirmation": "wrong"}).status_code
        == 422
    )
    assert client.get("/api/claims/CLM-1001").json()["payment"]
    result = client.post("/api/queue/reset", json={"confirmation": "RESET"})
    assert result.status_code == 200
    assert result.json() == {"reset_claims": 25}
    claims = client.get("/api/claims").json()
    assert all(
        c["status"] == "waiting" and c["decision"] is None and c["payment"] is None
        for c in claims
    )
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["thread_id"] is None
    assert claim["sign_off"] is None
    assert claim["story"] == source["story"]
    assert claim["documents"] == source["documents"]
    assert client.get("/api/claims/CLM-1001/activity").json() == []
    assert client.get(f"/api/policies/{source['policy_id']}").json() == policy
    assert client.get("/api/queue").json()["total"] == 0
    assert queue.reserve().total == 25


@pytest.mark.parametrize("mode", ["queue", "claim"])
def test_reset_is_blocked_while_work_is_active(client, mode):
    if mode == "queue":
        queue.reserve()
    else:
        workflow.start("CLM-1001")
    assert (
        client.post("/api/queue/reset", json={"confirmation": "RESET"}).status_code
        == 409
    )
    assert len(client.get("/api/claims/CLM-1001/activity").json()) == (
        1 if mode == "claim" else 0
    )
