from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient

from agent import api
from agent.claim import work_claim
from agent.queue import run_queue
from agent.tests.stubs import script, scripted
from backend import queue, store
from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "recovery.sqlite3"))
    with TestClient(app) as api_client:
        monkeypatch.setattr(api, "backend", lambda: nullcontext(api_client))
        yield api_client


def plan(claim_ids):
    """Plan a to-do list for the given claims."""
    return [
        ("list_waiting_claims", {}),
        (
            "set_todo_list",
            {
                "items": [
                    {"claim_id": claim_id, "title": f"Work {claim_id}"}
                    for claim_id in claim_ids
                ]
            },
        ),
    ]


def run_with(client, monkeypatch, calls, worker, cap):
    """Start a capped run whose agent makes the given tool calls."""
    monkeypatch.setattr(
        queue,
        "run_queue_agent",
        lambda run_id: run_queue(run_id, script(calls), worker),
    )
    response = client.post("/api/queue/run", json={"cap": cap})
    assert response.status_code == 202
    return client.get("/api/queue").json()


def deciding_worker(claim_id, thread_id):
    return work_claim(claim_id, thread_id, scripted("approve", "420.00"))


def test_one_failing_claim_does_not_stop_the_run(client, monkeypatch):
    def worker(claim_id, thread_id):
        if claim_id == "CLM-1001":
            raise TimeoutError("the model timed out")
        return deciding_worker(claim_id, thread_id)

    calls = [
        *plan(["CLM-1001", "CLM-1002"]),
        ("work_one_claim", {"claim_id": "CLM-1001"}),
        ("update_todo", {"claim_id": "CLM-1001", "state": "to_do", "note": "failed"}),
        ("work_one_claim", {"claim_id": "CLM-1002"}),
        ("update_todo", {"claim_id": "CLM-1002", "state": "done", "note": "worked"}),
        ("finish_run", {"summary": "One claim worked, one timed out."}),
    ]
    progress = run_with(client, monkeypatch, calls, worker, 2)
    assert progress["status"] == "finished"
    assert progress["summary"] == "One claim worked, one timed out."
    failed = client.get("/api/claims/CLM-1001").json()
    assert failed["status"] == "waiting"
    assert failed["attempts"] == 1
    assert failed["decision"] is None
    assert client.get("/api/claims/CLM-1002").json()["decision"]["outcome"] == "approve"
    assert "back in the queue to try again" in str(
        client.get("/api/claims/CLM-1001/activity").json()
    )


def test_a_failed_claim_is_tried_again_and_decided(client, monkeypatch):
    tries = []

    def worker(claim_id, thread_id):
        tries.append(claim_id)
        if tries.count(claim_id) == 1:
            raise ConnectionError("the provider was unavailable")
        return deciding_worker(claim_id, thread_id)

    calls = [
        *plan(["CLM-1001"]),
        ("work_one_claim", {"claim_id": "CLM-1001"}),
        ("list_waiting_claims", {}),
        ("work_one_claim", {"claim_id": "CLM-1001"}),
        ("update_todo", {"claim_id": "CLM-1001", "state": "done", "note": "retried"}),
        ("finish_run", {"summary": "Worked one claim after a retry."}),
    ]
    progress = run_with(client, monkeypatch, calls, worker, 1)
    assert progress["status"] == "finished"
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["decision"]["outcome"] == "approve"
    assert claim["attempts"] == 1
    assert tries == ["CLM-1001", "CLM-1001"]
    assert progress["worked"] == 1


def test_a_claim_that_fails_twice_is_left_for_a_handler(client, monkeypatch):
    with store.connect() as db:
        db.execute(
            "UPDATE claims SET status='decided', decision='{}' WHERE id!='CLM-1001'"
        )

    def worker(claim_id, thread_id):
        raise TimeoutError("the model timed out")

    calls = [
        *plan(["CLM-1001"]),
        ("work_one_claim", {"claim_id": "CLM-1001"}),
        ("work_one_claim", {"claim_id": "CLM-1001"}),
        ("work_one_claim", {"claim_id": "CLM-1001"}),
        (
            "update_todo",
            {
                "claim_id": "CLM-1001",
                "state": "left_for_handler",
                "note": "failed twice",
            },
        ),
        ("finish_run", {"summary": "One claim left for a handler."}),
    ]
    progress = run_with(client, monkeypatch, calls, worker, 5)
    assert progress["status"] == "finished"
    assert progress["todos"][0]["state"] == "left_for_handler"
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["attempts"] == 2
    assert claim["status"] == "waiting"
    assert claim["decision"] is None
    assert "left for a handler" in str(
        client.get("/api/claims/CLM-1001/activity").json()
    )
    assert progress["todos"][0]["note"] == "failed twice"


def test_a_decided_claim_is_never_worked_twice(client, monkeypatch):
    calls = [
        *plan(["CLM-1001"]),
        ("work_one_claim", {"claim_id": "CLM-1001"}),
        ("work_one_claim", {"claim_id": "CLM-1001"}),
        ("update_todo", {"claim_id": "CLM-1001", "state": "done", "note": "worked"}),
        ("finish_run", {"summary": "Worked one claim."}),
    ]
    progress = run_with(client, monkeypatch, calls, deciding_worker, 1)
    assert progress["status"] == "finished"
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["decision"]["payout"] == "420.00"
    assert claim["payment"]["amount"] == "420.00"
    assert (
        len(
            [
                event
                for event in client.get("/api/claims/CLM-1001/activity").json()
                if "Simulated payment" in event["message"]
            ]
        )
        == 1
    )


def test_the_run_cannot_close_over_a_missed_claim(client, monkeypatch):
    calls = [
        *plan(["CLM-1001", "CLM-1002"]),
        ("work_one_claim", {"claim_id": "CLM-1001"}),
        ("finish_run", {"summary": "Too soon."}),
        ("list_waiting_claims", {}),
        ("work_one_claim", {"claim_id": "CLM-1002"}),
        ("finish_run", {"summary": "Worked both claims."}),
    ]
    progress = run_with(client, monkeypatch, calls, deciding_worker, 2)
    assert progress["status"] == "finished"
    assert progress["summary"] == "Worked both claims."
    assert progress["worked"] == 2
    assert client.get("/api/claims/CLM-1002").json()["decision"]


def test_finish_is_refused_while_a_claim_inside_the_cap_waits(client, monkeypatch):
    seen = []

    def watcher(run_id):
        waiting = client.get(f"/api/queue/{run_id}/waiting").json()
        seen.append(waiting["remaining"])
        response = client.post(
            f"/api/queue/{run_id}/finish", json={"summary": "Nothing done."}
        )
        seen.append(response.status_code)
        seen.append(response.json()["detail"])

    monkeypatch.setattr(queue, "run_queue_agent", watcher)
    client.post("/api/queue/run", json={"cap": 2})
    assert seen[0] == 2
    assert seen[1] == 409
    assert "Still waiting inside this run's cap: CLM-1001" in seen[2]
    assert client.get("/api/queue").json()["status"] == "stopped"
