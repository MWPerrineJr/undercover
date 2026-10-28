"""SQLite storage with an explicit seed-file allowlist."""

import json
import os
import re
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
    thread_id TEXT, running INTEGER NOT NULL DEFAULT 0,
    decision TEXT, sign_off TEXT, payment TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    CHECK(payment IS NULL OR decision IS NOT NULL),
    CHECK(sign_off IS NULL OR decision IS NOT NULL)
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, cap INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK(status IN ('running','finished','stopped')),
    summary TEXT,
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS run_claims (
    run_id TEXT NOT NULL REFERENCES runs(id),
    claim_id TEXT NOT NULL REFERENCES claims(id),
    PRIMARY KEY (run_id, claim_id)
);
CREATE TABLE IF NOT EXISTS todos (
    run_id TEXT NOT NULL REFERENCES runs(id),
    claim_id TEXT NOT NULL REFERENCES claims(id),
    position INTEGER NOT NULL, title TEXT NOT NULL, note TEXT,
    state TEXT NOT NULL DEFAULT 'to_do'
        CHECK(state IN ('to_do','in_progress','done','left_for_handler')),
    PRIMARY KEY (run_id, claim_id)
);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id),
    thread_id TEXT NOT NULL, message TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'step' CHECK(kind IN ('step','read')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""
ATTEMPT_LIMIT = 2
DOCUMENTS = (
    ("wording", "policy_wording.md", "2026.1"),
    ("manual", "claims_manual.md", "2026.2"),
)


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
        columns = {row["name"] for row in db.execute("PRAGMA table_info(claims)")}
        if "running" not in columns:
            db.execute(
                "ALTER TABLE claims ADD COLUMN running INTEGER NOT NULL DEFAULT 0"
            )
        if "attempts" not in columns:
            db.execute(
                "ALTER TABLE claims ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0"
            )
        events = {row["name"] for row in db.execute("PRAGMA table_info(activity)")}
        if "kind" not in events:
            db.execute(
                "ALTER TABLE activity ADD COLUMN kind TEXT NOT NULL DEFAULT 'step'"
            )
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
        for kind, filename, version in DOCUMENTS:
            db.execute(
                "INSERT OR IGNORE INTO records VALUES (?, ?, ?)",
                (
                    kind,
                    kind,
                    json.dumps(
                        {"text": (DATA / filename).read_text(), "version": version}
                    ),
                ),
            )
        for raw in json.loads((DATA / "claims.json").read_text()):
            claim = Claim.model_validate(raw)
            db.execute(
                "INSERT OR IGNORE INTO claims (id, body) VALUES (?, ?)",
                (claim.claim_id, claim.model_dump_json()),
            )


def sections(text: str) -> list[dict]:
    """Split a document on its numbered `## N. Title` headings."""
    parts = re.split(r"^## (\d+)\. (.+)$", text, flags=re.MULTILINE)
    return [
        {
            "number": int(number),
            "title": title,
            "text": f"## {number}. {title}\n\n{body.strip()}",
        }
        for number, title, body in zip(
            parts[1::3], parts[2::3], parts[3::3], strict=True
        )
    ]


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
    result.update(
        {
            "status": row["status"],
            "thread_id": row["thread_id"],
            "running": bool(row["running"]),
            "attempts": row["attempts"],
        }
    )
    for field in ("decision", "sign_off", "payment"):
        result[field] = json.loads(row[field]) if row[field] else None
    if result["decision"]:
        result["decision"].setdefault("manual_sections", [])
    result["left_for_handler"] = (
        row["attempts"] >= ATTEMPT_LIMIT and result["decision"] is None
    )
    return result


def event(db, claim_id: str, thread_id: str, message: str, kind: str = "step"):
    """Append a timestamped step or document read."""
    db.execute(
        "INSERT INTO activity (claim_id, thread_id, message, kind) VALUES (?, ?, ?, ?)",
        (claim_id, thread_id, message, kind),
    )
