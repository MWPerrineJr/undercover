"""The policy wording and the claims manual, looked up section by section."""

from fastapi import APIRouter

from backend import store

router = APIRouter(prefix="/api/documents")
NAMES = {"policy_wording": "Policy wording", "claims_manual": "Claims manual"}


def contents(db, document: str) -> dict:
    """Read a document's version and its sections."""
    if document not in NAMES:
        raise LookupError("Document not found")
    kind = "wording" if document == "policy_wording" else "manual"
    held = store.record(db, kind, kind)
    return {
        "document": document,
        "title": NAMES[document],
        "version": held["version"],
        "sections": store.sections(held["text"]),
    }


@router.get("", operation_id="list_documents")
def list_documents() -> list[dict]:
    """List both documents with the number and title of every section."""
    with store.connect() as db:
        documents = [contents(db, document) for document in NAMES]
    for document in documents:
        document["sections"] = [
            {"number": section["number"], "title": section["title"]}
            for section in document["sections"]
        ]
    return documents


@router.get("/search", operation_id="search_documents")
def search_documents(q: str) -> list[dict]:
    """Find the sections of either document that mention every given word."""
    words = q.lower().split()
    found = []
    with store.connect() as db:
        documents = [contents(db, document) for document in NAMES]
    for document in documents:
        for section in document["sections"]:
            lines = section["text"].splitlines()
            matched = [
                line for line in lines if all(word in line.lower() for word in words)
            ]
            if not matched and not all(
                word in section["text"].lower() for word in words
            ):
                continue
            found.append(
                {
                    "document": document["document"],
                    "document_title": document["title"],
                    "number": section["number"],
                    "title": section["title"],
                    "excerpt": (matched[0] if matched else lines[2])[:240],
                }
            )
    return found


@router.get("/{document}/sections/{number}", operation_id="read_section")
def read_section(document: str, number: int) -> dict:
    """Read one numbered section of a document."""
    with store.connect() as db:
        held = contents(db, document)
    for section in held["sections"]:
        if section["number"] == number:
            return {
                "document": held["document"],
                "document_title": held["title"],
                "version": held["version"],
                **section,
            }
    raise LookupError("Section not found")
