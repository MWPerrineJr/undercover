from contextlib import nullcontext

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent import api, main
from agent import claim as claim_agent
from agent import model as model_module
from agent.tests.stubs import StubModel, scripted
from agent.tools import tools_for
from backend import store, workflow
from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "agent.sqlite3"))
    with TestClient(app) as client:
        monkeypatch.setattr(api, "backend", lambda: nullcontext(client))
        yield client


@pytest.mark.parametrize(
    ("outcome", "amount", "status", "report"),
    [
        ("approve", "420.00", "decided", "CLM-1001 approve $420.00 paid"),
        (
            "approve",
            "1250.00",
            "waiting_for_sign_off",
            "CLM-1001 approve $1,250.00 waiting for sign-off",
        ),
        ("decline", "0", "decided", "CLM-1001 decline $0.00"),
        ("refer", "0", "decided", "CLM-1001 refer $0.00"),
    ],
)
def test_run(client, outcome, amount, status, report):
    thread = workflow.start("CLM-1001")["thread_id"]
    assert main.run("CLM-1001", thread, scripted(outcome, amount)) == report
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == status
    assert claim["decision"]["outcome"] == outcome
    assert bool(claim["payment"]) == (outcome == "approve" and status == "decided")
    activity = client.get("/api/claims/CLM-1001/activity").json()
    reads = [a["message"] for a in activity if a["kind"] == "read"]
    assert reads == [
        "Read Policy wording section 3: Trip Delay",
        "Read Claims manual section 9: Repeat claims",
    ]
    assert all(a["thread_id"] == thread for a in activity)
    assert not any("evals" in a["message"] for a in activity)


def test_each_claim_starts_clean_and_reports_a_line(client):
    first, second = (
        workflow.start(claim_id)["thread_id"] for claim_id in ("CLM-1001", "CLM-1002")
    )
    models = [scripted(), scripted("decline", "0", False)]
    assert claim_agent.work_claim("CLM-1001", first, models[0]) == (
        "CLM-1001 approve $420.00 paid"
    )
    assert claim_agent.work_claim("CLM-1002", second, models[1]) == (
        "CLM-1002 decline $0.00"
    )
    assert first != second
    later = str(models[1].seen)
    assert "CLM-1001" not in later
    assert first not in later
    assert all(
        "CLM-1002" not in event["message"]
        for event in client.get("/api/claims/CLM-1001/activity").json()
    )
    assert all(
        event["thread_id"] == second
        for event in client.get("/api/claims/CLM-1002/activity").json()
    )


def test_a_run_that_saves_nothing_reports_failure(client):
    thread = workflow.start("CLM-1001")["thread_id"]
    model = StubModel(messages=iter([AIMessage(content="I am stuck.")]))
    assert main.run("CLM-1001", thread, model) == "CLM-1001 failed: no decision saved"


def test_invalid_tool_output(client):
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
                                "manual_sections": [],
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
    assert model_module.model().model_name == "openai/gpt-6-luna"
    assert model_module.model().reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert model_module.model().model_name == "openrouter/free"
    assert model_module.model().reasoning_effort is None
    monkeypatch.setenv("BACKEND_URL", "http://example.invalid")
    with api.backend() as client:
        assert str(client.base_url) == "http://example.invalid"


def test_unavailable_instructions(client, monkeypatch):
    def unavailable():
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(api, "backend", unavailable)
    with pytest.raises(httpx.ConnectError):
        main.run("CLM-1001", "test", scripted())


def test_tools_cover_lookup_not_whole_documents(client):
    names = {t.name for t in tools_for("CLM-1001", "thread")}
    assert names == {
        "read_claim",
        "read_policy",
        "read_customer",
        "read_plans",
        "list_documents",
        "search_documents",
        "read_section",
        "record_decision",
        "pay_claim",
    }


def test_missing_section_is_reported_to_the_agent(client):
    thread = workflow.start("CLM-1001")["thread_id"]
    tools = {t.name: t for t in tools_for("CLM-1001", thread)}
    reply = tools["read_section"].invoke({"document": "claims_manual", "number": 99})
    assert "Section not found" in reply
    assert not [
        a
        for a in client.get("/api/claims/CLM-1001/activity").json()
        if a["kind"] == "read"
    ]
