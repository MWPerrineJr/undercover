import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import store
from backend.main import app


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.sqlite3"))
    store.initialize()


@pytest.mark.usefixtures("database")
def test_seed_records_and_restart():
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM claims").fetchone()[0] == 25
        assert (
            db.execute("SELECT count(*) FROM records WHERE kind='handlers'").fetchone()[
                0
            ]
            == 3
        )
        for source in json.loads((store.DATA / "claims.json").read_text()):
            claim = store.claim_record(db, source["claim_id"])
            assert claim["status"] == "waiting"
            for field in ("story", "documents", "items"):
                assert claim[field] == source[field]
            policy = store.record(db, "policies", claim["policy_id"])
            customer = store.record(db, "customers", claim["customer_id"])
            assert policy["customer_id"] == customer["customer_id"]
            assert policy["plan"] in {
                p["plan"] for p in store.record(db, "plans", "plans")["plans"]
            }
        for kind in ("policies", "customers", "handlers"):
            for raw in json.loads((store.DATA / f"{kind}.json").read_text()):
                key = {
                    "policies": "policy_id",
                    "customers": "customer_id",
                    "handlers": "handler_id",
                }[kind]
                assert store.record(db, kind, raw[key]) == raw
        assert (
            store.record(db, "wording", "wording")["text"]
            == (store.DATA / "policy_wording.md").read_text()
        )
        db.execute(
            "UPDATE claims SET status='decided', decision='{}' WHERE id='CLM-1001'"
        )
        store.event(db, "CLM-1001", "test", "Completed")
    store.initialize()
    with store.connect() as db:
        assert store.claim_record(db, "CLM-1001")["decision"] == {}
        assert db.execute("SELECT count(*) FROM activity").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM claims").fetchone()[0] == 25
        with pytest.raises(LookupError):
            store.claim_record(db, "missing")
        with pytest.raises(LookupError):
            store.record(db, "customers", "missing")


def test_seed_file_allowlist(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "allowlist.sqlite3"))
    opened = []
    original = Path.read_text

    def tracked(path, *args, **kwargs):
        opened.append(path.name)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracked)
    store.initialize()
    assert set(opened) == {
        "company.json",
        "plans.json",
        "policies.json",
        "customers.json",
        "handlers.json",
        "claims.json",
        "policy_wording.md",
    }


@pytest.mark.usefixtures("database")
def test_startup():
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
