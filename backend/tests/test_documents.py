import re

import pytest

from backend import store


def headings(filename: str) -> list[tuple[int, str]]:
    text = (store.DATA / filename).read_text()
    return [
        (int(number), title)
        for number, title in re.findall(r"^## (\d+)\. (.+)$", text, flags=re.MULTILINE)
    ]


def test_contents_match_the_source_documents(client):
    documents = {d["document"]: d for d in client.get("/api/documents").json()}
    assert set(documents) == {"policy_wording", "claims_manual"}
    for name, filename in (
        ("policy_wording", "policy_wording.md"),
        ("claims_manual", "claims_manual.md"),
    ):
        listed = [(s["number"], s["title"]) for s in documents[name]["sections"]]
        assert listed == headings(filename)
    assert len(documents["policy_wording"]["sections"]) == 12
    assert len(documents["claims_manual"]["sections"]) == 14
    assert documents["claims_manual"]["version"] == "2026.2"
    assert "text" not in documents["claims_manual"]["sections"][0]


def test_read_one_section_only(client):
    section = client.get("/api/documents/claims_manual/sections/9").json()
    assert section["title"] == "Repeat claims"
    assert section["document_title"] == "Claims manual"
    assert "third claim within any 12 month period" in section["text"]
    assert "Meals without receipts" not in section["text"]
    assert "the documents do not support" not in section["text"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/documents/claims_manual/sections/99",
        "/api/documents/staff_handbook/sections/1",
    ],
)
def test_missing_sections(client, path):
    assert client.get(path).status_code == 404


@pytest.mark.parametrize(
    ("query", "document", "number"),
    [
        ("wild animal", "claims_manual", 7),
        ("meals without receipts", "claims_manual", 10),
        ("baggage delay", "policy_wording", 4),
    ],
)
def test_search_finds_the_section(client, query, document, number):
    found = client.get("/api/documents/search", params={"q": query}).json()
    assert (document, number) in [(f["document"], f["number"]) for f in found]
    assert all(f["excerpt"] for f in found)


def test_search_without_a_match(client):
    assert client.get("/api/documents/search", params={"q": "zyzzyva"}).json() == []
