import pytest

from backend import queue, store


@pytest.fixture
def idle(monkeypatch):
    """Start runs without letting any agent act."""
    monkeypatch.setattr(queue, "run_queue_agent", lambda run_id: "Nothing to do")


def start(client, cap=5):
    response = client.post("/api/queue/run", json={"cap": cap})
    assert response.status_code == 202
    return response.json()["run_id"]


@pytest.mark.usefixtures("idle")
def test_run_record_and_conflicts(client):
    assert client.get("/api/queue").json() == {**queue.IDLE}
    run_id = start(client, 2)
    progress = client.get("/api/queue").json()
    assert progress["run_id"] == run_id
    assert progress["cap"] == 2
    assert progress["status"] == "stopped"
    assert progress["summary"] == "Run ended without a summary"
    assert client.post("/api/queue/run", json={"cap": 0}).status_code == 422
    assert (
        client.post(f"/api/queue/{run_id}/finish", json={"summary": "x"}).status_code
        == 409
    )
    assert (
        client.post(
            "/api/queue/missing/todos/CLM-1001", json={"state": "done", "note": ""}
        ).status_code
        == 404
    )


def test_one_active_run_at_a_time(client, monkeypatch):
    def second_run(run_id):
        assert client.post("/api/queue/run", json={"cap": 1}).status_code == 409

    monkeypatch.setattr(queue, "run_queue_agent", second_run)
    start(client, 1)


def test_the_cap_bounds_what_the_agent_may_take(client, monkeypatch):
    taken = []

    def greedy(run_id):
        waiting = client.get(f"/api/queue/{run_id}/waiting").json()
        assert waiting["remaining"] == 2
        assert len(waiting["claims"]) == 25
        for claim_id in ("CLM-1001", "CLM-1002", "CLM-1003"):
            taken.append(
                client.post(f"/api/queue/{run_id}/claims/{claim_id}/start").status_code
            )
        assert client.get(f"/api/queue/{run_id}/waiting").json()["remaining"] == 0

    monkeypatch.setattr(queue, "run_queue_agent", greedy)
    start(client, 2)
    assert taken == [200, 200, 409]
    assert client.get("/api/claims/CLM-1003").json()["status"] == "waiting"


def test_todos_and_claim_handover(client, monkeypatch):
    def plan_and_work(run_id):
        items = {"items": [{"claim_id": "CLM-1001", "title": "Rome delay"}]}
        assert client.post(f"/api/queue/{run_id}/todos", json=items).status_code == 200
        assert (
            client.post(
                f"/api/queue/{run_id}/todos",
                json={"items": [{"claim_id": "missing", "title": "x"}]},
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/queue/{run_id}/todos/CLM-1002",
                json={"state": "done", "note": ""},
            ).status_code
            == 404
        )
        started = client.post(f"/api/queue/{run_id}/claims/CLM-1001/start").json()
        assert client.get("/api/claims/CLM-1001").json()["running"]
        assert (
            client.post(f"/api/queue/{run_id}/claims/CLM-1001/start").status_code == 409
        )
        client.post(
            f"/api/queue/{run_id}/claims/CLM-1001/finish",
            json={"thread_id": started["thread_id"], "report": "CLM-1001 refer $0.00"},
        )
        client.post(
            f"/api/queue/{run_id}/todos/CLM-1001",
            json={"state": "done", "note": "CLM-1001 refer $0.00"},
        )
        client.post(f"/api/queue/{run_id}/finish", json={"summary": "One claim seen."})

    monkeypatch.setattr(queue, "run_queue_agent", plan_and_work)
    start(client, 1)
    progress = client.get("/api/queue").json()
    assert progress["status"] == "finished"
    assert progress["summary"] == "One claim seen."
    assert progress["todos"] == [
        {
            "claim_id": "CLM-1001",
            "title": "Rome delay",
            "state": "done",
            "note": "CLM-1001 refer $0.00",
        }
    ]
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "waiting"
    assert not claim["running"]
    assert "Run finished: CLM-1001 refer $0.00" in str(
        client.get("/api/claims/CLM-1001/activity").json()
    )


def test_a_failing_agent_leaves_the_run_stopped(client, monkeypatch):
    def failing(run_id):
        raise RuntimeError("Do not expose this secret")

    monkeypatch.setattr(queue, "run_queue_agent", failing)
    start(client)
    progress = client.get("/api/queue").json()
    assert progress["status"] == "stopped"
    assert "secret" not in progress["summary"]


@pytest.mark.usefixtures("idle")
def test_no_waiting_claims(client):
    with store.connect() as db:
        db.execute("UPDATE claims SET status='decided', decision='{}'")
    assert client.post("/api/queue/run", json={"cap": 1}).status_code == 409


def test_recovery_marks_an_interrupted_run_stopped(client, monkeypatch):
    def interrupted(run_id):
        client.post(
            f"/api/queue/{run_id}/todos",
            json={"items": [{"claim_id": "CLM-1001", "title": "Rome delay"}]},
        )
        client.post(
            f"/api/queue/{run_id}/todos/CLM-1001",
            json={"state": "in_progress", "note": ""},
        )
        with store.connect() as db:
            db.execute("UPDATE runs SET status='running'")

    monkeypatch.setattr(queue, "run_queue_agent", interrupted)
    start(client)
    with store.connect() as db:
        db.execute("UPDATE runs SET status='running'")
    queue.recover()
    progress = client.get("/api/queue").json()
    assert progress["status"] == "stopped"
    assert "interrupted" in progress["summary"]
    assert progress["todos"][0]["state"] == "to_do"


def test_reset_needs_confirmation_and_an_idle_queue(client, monkeypatch):
    def reset_during_run(run_id):
        assert (
            client.post("/api/queue/reset", json={"confirmation": "RESET"}).status_code
            == 409
        )
        client.post(f"/api/queue/{run_id}/claims/CLM-1001/start")

    monkeypatch.setattr(queue, "run_queue_agent", reset_during_run)
    start(client, 1)
    assert (
        client.post("/api/queue/reset", json={"confirmation": "reset"}).status_code
        == 422
    )
    assert client.post("/api/queue/reset", json={}).status_code == 422
    assert client.get("/api/claims/CLM-1001").json()["running"]
    with store.connect() as db:
        db.execute("UPDATE claims SET running=0")
    assert client.post("/api/queue/reset", json={"confirmation": "RESET"}).json() == {
        "reset_claims": 25
    }
    assert client.get("/api/queue").json() == {**queue.IDLE}
    assert client.get("/api/claims/CLM-1001/activity").json() == []
