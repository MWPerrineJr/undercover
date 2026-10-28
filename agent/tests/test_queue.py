from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient

from agent import api
from agent.claim import work_claim
from agent.queue import run_queue
from agent.tests.stubs import queue_script, scripted
from backend import queue
from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "queue.sqlite3"))
    with TestClient(app) as api_client:
        monkeypatch.setattr(api, "backend", lambda: nullcontext(api_client))
        yield api_client


def scripted_worker(claim_id, thread_id):
    """Work a claim with the real claim agent and a scripted model."""
    amounts = {"CLM-1002": ("approve", "1250.00"), "CLM-1003": ("decline", "0")}
    outcome, amount = amounts.get(claim_id, ("approve", "420.00"))
    return work_claim(
        claim_id, thread_id, scripted(outcome, amount, outcome == "approve")
    )


def start_run(client, cap):
    response = client.post("/api/queue/run", json={"cap": cap})
    assert response.status_code == 202
    return response.json()["run_id"]


def test_a_capped_run_works_only_its_cap(client, monkeypatch):
    planned = ["CLM-1001", "CLM-1002", "CLM-1003"]
    monkeypatch.setattr(
        queue,
        "run_queue_agent",
        lambda run_id: run_queue(run_id, queue_script(planned), scripted_worker),
    )
    start_run(client, 3)
    progress = client.get("/api/queue").json()
    assert progress["status"] == "finished"
    assert progress["summary"] == "Worked 3 claims."
    assert progress["worked"] == 3
    assert [t["claim_id"] for t in progress["todos"]] == planned
    assert {t["state"] for t in progress["todos"]} == {"done"}
    claims = client.get("/api/claims").json()
    decided = [c for c in claims if c["decision"]]
    assert sorted(c["claim_id"] for c in decided) == planned
    assert len([c for c in claims if c["status"] == "waiting"]) == 22


def test_the_agent_chooses_the_order(client, monkeypatch):
    chosen = ["CLM-1007", "CLM-1002"]
    monkeypatch.setattr(
        queue,
        "run_queue_agent",
        lambda run_id: run_queue(run_id, queue_script(chosen), scripted_worker),
    )
    start_run(client, 5)
    progress = client.get("/api/queue").json()
    assert [t["claim_id"] for t in progress["todos"]] == chosen
    assert progress["worked"] == 2
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"
    assert client.get("/api/claims/CLM-1002").json()["decision"]["payout"] == "1250.00"


def test_the_cap_is_enforced_against_the_agent(client, monkeypatch):
    too_many = ["CLM-1001", "CLM-1002", "CLM-1003"]
    monkeypatch.setattr(
        queue,
        "run_queue_agent",
        lambda run_id: run_queue(run_id, queue_script(too_many), scripted_worker),
    )
    start_run(client, 2)
    progress = client.get("/api/queue").json()
    assert progress["worked"] == 2
    assert progress["status"] == "finished"
    assert client.get("/api/claims/CLM-1003").json()["status"] == "waiting"


def test_a_todo_item_is_in_progress_while_its_claim_is_worked(client, monkeypatch):
    seen = []

    def watching_worker(claim_id, thread_id):
        seen.append(
            {
                t["claim_id"]: t["state"]
                for t in client.get("/api/queue").json()["todos"]
            }
        )
        return scripted_worker(claim_id, thread_id)

    monkeypatch.setattr(
        queue,
        "run_queue_agent",
        lambda run_id: run_queue(
            run_id, queue_script(["CLM-1001", "CLM-1002"]), watching_worker
        ),
    )
    start_run(client, 2)
    assert seen[0] == {"CLM-1001": "in_progress", "CLM-1002": "to_do"}
    assert seen[1] == {"CLM-1001": "done", "CLM-1002": "in_progress"}
