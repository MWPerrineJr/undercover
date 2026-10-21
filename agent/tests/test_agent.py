from contextlib import nullcontext

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent import main
from agent.tests.stubs import StubModel, scripted
from backend import store, workflow
from backend.main import app


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "agent.sqlite3"))
    with TestClient(app) as client:
        monkeypatch.setattr(main, "backend", lambda: nullcontext(client))
        yield client


@pytest.mark.parametrize(
    ("outcome", "amount", "status"),
    [
        ("approve", "420.00", "decided"),
        ("approve", "1250.00", "waiting_for_sign_off"),
        ("decline", "0", "decided"),
        ("refer", "0", "decided"),
    ],
)
def test_run(api, outcome, amount, status):
    thread = workflow.start("CLM-1001")["thread_id"]
    assert (
        main.run("CLM-1001", thread, scripted(outcome, amount))
        == "Claim processing complete."
    )
    claim = api.get("/api/claims/CLM-1001").json()
    assert claim["status"] == status
    assert claim["decision"]["outcome"] == outcome
    assert bool(claim["payment"]) == (outcome == "approve" and status == "decided")
    activity = api.get("/api/claims/CLM-1001/activity").json()
    assert any("/policy-wording" in a["message"] for a in activity)
    assert all(a["thread_id"] == thread for a in activity)
    assert not any("evals" in a["message"] for a in activity)


def test_invalid_tool_output(api):
    thread = workflow.start("CLM-1001")["thread_id"]
    model = StubModel(
        messages=iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "record_decision",
                            "args": {
                                "outcome": "wrong",
                                "payout": "0",
                                "calculation": "Test",
                                "explanation": "Test",
                                "policy_sections": [3],
                            },
                            "id": "1",
                        }
                    ],
                ),
                AIMessage(content="No valid decision."),
            ]
        )
    )
    main.run("CLM-1001", thread, model)
    with store.connect() as db:
        assert store.claim_record(db, "CLM-1001")["decision"] is None


def test_model_name_and_http_client(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    assert main.model().reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
    assert main.model().reasoning_effort is None
    monkeypatch.setenv("BACKEND_URL", "http://example.invalid")
    with main.backend() as client:
        assert str(client.base_url) == "http://example.invalid"


def test_unavailable_instructions(api, monkeypatch):
    def unavailable():
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(main, "backend", unavailable)
    with pytest.raises(httpx.ConnectError):
        main.run("CLM-1001", "test", scripted())
