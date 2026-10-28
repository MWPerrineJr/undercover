from contextlib import nullcontext

import httpx
import pytest
from fastapi.testclient import TestClient

from agent import __main__ as cli
from agent import api
from backend import queue, runs
from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "cli.sqlite3"))
    monkeypatch.setattr(queue, "run_queue_agent", lambda run_id: "Nothing to do")
    monkeypatch.setattr(runs, "run_agent", lambda claim_id, thread_id: "worked")
    with TestClient(app) as api_client:
        monkeypatch.setattr(api, "backend", lambda: nullcontext(api_client))
        yield api_client


def test_a_capped_run_from_the_command_line(client, capsys):
    assert cli.main(["--cap", "2"]) == 0
    assert '"cap":2' in capsys.readouterr().out
    assert client.get("/api/queue").json()["cap"] == 2


def test_one_named_claim_from_the_command_line(client, capsys):
    assert cli.main(["--claim", "CLM-1001"]) == 0
    assert "thread_id" in capsys.readouterr().out
    assert client.get("/api/claims/CLM-1001").json()["thread_id"]


def test_a_rejected_request_exits_non_zero(client, capsys):
    assert cli.main(["--claim", "CLM-9999"]) == 1
    assert "Claim not found" in capsys.readouterr().out


def test_an_unreachable_backend_exits_non_zero(monkeypatch, capsys):
    def offline():
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(api, "backend", offline)
    assert cli.main(["--cap", "1"]) == 1
    assert "not reachable" in capsys.readouterr().out


def test_one_of_cap_or_claim_is_required():
    with pytest.raises(SystemExit):
        cli.main([])
