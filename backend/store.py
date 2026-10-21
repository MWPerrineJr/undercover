"""SQLite storage with an explicit seed-file allowlist."""

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from backend.models import Claim, Customer, Handler, Policy

DATA = Path(__file__).resolve().parents[1] / "data"
SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY (kind, id)
);
CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY, body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'waiting'
        CHECK(status IN ('waiting','in_progress','waiting_for_sign_off','decided')),
    thread_id TEXT, decision TEXT, sign_off TEXT, payment TEXT,
    CHECK(payment IS NULL OR decision IS NOT NULL),
    CHECK(sign_off IS NULL OR decision IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id),
    thread_id TEXT NOT NULL, message TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""


@contextmanager
def connect():
    """Commit successful operations and roll back failures."""
    path = Path(os.getenv("UNDERCOVER_DB", "undercover.sqlite3"))
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize():
    """Insert missing seed records without replacing saved work."""
    with connect() as db:
        db.executescript(SCHEMA)
        for kind, model in (
            ("customers", Customer),
            ("policies", Policy),
            ("handlers", Handler),
        ):
            for raw in json.loads((DATA / f"{kind}.json").read_text()):
                record = model.model_validate(raw)
                key = raw[f"{kind[:-1] if kind != 'policies' else 'policy'}_id"]
                db.execute(
                    "INSERT OR IGNORE INTO records VALUES (?, ?, ?)",
                    (kind, key, record.model_dump_json()),
                )
        for name in ("company", "plans"):
            body = (DATA / f"{name}.json").read_text()
            db.execute(
                "INSERT OR IGNORE INTO records VALUES (?, ?, ?)", (name, name, body)
            )
        db.execute(
            "INSERT OR IGNORE INTO records VALUES (?, ?, ?)",
            (
                "wording",
                "wording",
                json.dumps(
                    {
                        "text": (DATA / "policy_wording.md").read_text(),
                        "version": "2026.1",
                    }
                ),
            ),
        )
        for raw in json.loads((DATA / "claims.json").read_text()):
            claim = Claim.model_validate(raw)
            db.execute(
                "INSERT OR IGNORE INTO claims (id, body) VALUES (?, ?)",
                (claim.claim_id, claim.model_dump_json()),
            )


def record(db, kind: str, key: str) -> dict:
    """Read one named business record."""
    row = db.execute(
        "SELECT body FROM records WHERE kind = ? AND id = ?", (kind, key)
    ).fetchone()
    if row is None:
        raise LookupError("Record not found")
    return json.loads(row["body"])


def claim_record(db, claim_id: str) -> dict:
    """Read a claim with its persisted workflow."""
    row = db.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if row is None:
        raise LookupError("Claim not found")
    result = json.loads(row["body"])
    result.update({"status": row["status"], "thread_id": row["thread_id"]})
    for field in ("decision", "sign_off", "payment"):
        result[field] = json.loads(row[field]) if row[field] else None
    return result


def event(db, claim_id: str, thread_id: str, message: str):
    """Append a timestamped operational event."""
    db.execute(
        "INSERT INTO activity (claim_id, thread_id, message) VALUES (?, ?, ?)",
        (claim_id, thread_id, message),
    )
