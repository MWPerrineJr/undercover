import inspect
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.routing import APIRoute

from backend import store, workflow
from backend.main import app


def decision(client, amount="1000.01", outcome="approve", claim_id="CLM-1001"):
    thread = workflow.start(claim_id)["thread_id"]
    body = {
        "thread_id": thread,
        "outcome": outcome,
        "payout": amount,
        "calculation": "Synthetic fixture: eligible expenses less offsets.",
        "explanation": "This is a synthetic decision. See the cited policy sections.",
        "policy_sections": [3, 10],
        "manual_sections": [6],
    }
    return thread, body, client.post(f"/api/claims/{claim_id}/decision", json=body)


def test_read_api(client):
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["story"]
    assert len(claim["documents"]) == 4
    assert client.get(f"/api/policies/{claim['policy_id']}").json()["trip"]
    assert client.get(f"/api/customers/{claim['customer_id']}").json()[
        "previous_claims"
    ]
    assert len(client.get("/api/plans").json()["plans"]) == 3
    assert "## 10." in client.get("/api/policy-wording").json()["text"]
    assert client.get("/api/claims/CLM-1001/policy").json()["trip"]
    assert client.get("/api/claims/CLM-1001/customer").json()["previous_claims"]
    names = {i["name"]: i for i in client.get("/api/instructions").json()}
    assert set(names) == {"queue", "claim"}
    assert "claims manual" in names["claim"]["text"]
    assert "work_one_claim" in names["queue"]["text"]
    assert not any("eval" in text["text"].lower() for text in names.values())
    assert client.get("/api/instructions/claim").json() == names["claim"]
    assert client.get("/api/instructions/missing").status_code == 404
    assert len(client.get("/api/handlers").json()) == 3
    assert client.get("/api/claims/CLM-1001/activity").json() == []
    for route in (
        "claims/missing",
        "customers/missing",
        "policies/missing",
        "claims/missing/activity",
    ):
        assert client.get(f"/api/{route}").status_code == 404
    assert client.get("/api/evals").status_code == 404


def test_openapi_required_inputs(client):
    schema = client.get("/openapi.json").json()
    ids = []
    for path in schema["paths"].values():
        for operation in path.values():
            ids.append(operation["operationId"])
            assert all(p["required"] for p in operation.get("parameters", []))
            if "requestBody" in operation:
                assert operation["requestBody"]["required"]
    assert len(ids) == len(set(ids))
    for name in ("Decision", "SignOff", "Payment"):
        model = schema["components"]["schemas"][name]
        assert set(model["required"]) == set(model["properties"])
    for route in app.routes:
        if isinstance(route, APIRoute):
            assert route.operation_id
            assert len((inspect.getdoc(route.endpoint) or "").splitlines()) == 1


def test_boundary_and_sign_off(client):
    thread, body, response = decision(client)
    assert response.status_code == 200
    assert response.json()["status"] == "waiting_for_sign_off"
    pay = {"thread_id": thread, "amount": "1000.01"}
    url = "/api/claims/CLM-1001"
    assert client.post(f"{url}/payment", json=pay).status_code == 409
    assert client.get(url).json()["payment"] is None
    assert (
        client.post(
            f"{url}/sign-off", json={"thread_id": thread, "handler_id": "missing"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{url}/sign-off", json={"thread_id": "stale", "handler_id": "HND-01"}
        ).status_code
        == 409
    )
    assert client.post(f"{url}/decision", json=body).status_code == 409
    with store.connect() as db:
        handler = store.record(db, "handlers", "HND-02")
        handler["can_approve_over_limit"] = False
        db.execute(
            "UPDATE records SET body=? WHERE kind='handlers' AND id='HND-02'",
            (json.dumps(handler),),
        )
    assert (
        client.post(
            f"{url}/sign-off", json={"thread_id": thread, "handler_id": "HND-02"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{url}/sign-off", json={"thread_id": thread, "handler_id": "HND-01"}
        ).status_code
        == 200
    )
    assert (
        client.post(f"{url}/payment", json={**pay, "amount": "1000"}).status_code == 409
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(f"{url}/payment", json=pay).status_code, range(2)
            )
        )
    assert sorted(responses) == [200, 409]
    assert client.get(url).json()["status"] == "decided"
    assert any(
        "Simulated payment" in e["message"]
        for e in client.get(f"{url}/activity").json()
    )


@pytest.mark.parametrize(
    ("outcome", "amount"), [("approve", "1000"), ("decline", "0"), ("refer", "0")]
)
def test_outcomes(client, outcome, amount):
    thread, body, response = decision(client, amount, outcome)
    assert response.status_code == 200
    payment = client.post(
        "/api/claims/CLM-1001/payment", json={"thread_id": thread, "amount": amount}
    )
    assert payment.status_code == (200 if outcome == "approve" else 409)
    assert client.get("/api/claims/CLM-1001").json()["status"] == "decided"
    assert (
        client.post(
            "/api/claims/CLM-1001/decision", json={**body, "thread_id": "stale"}
        ).status_code
        == 409
    )


@pytest.mark.parametrize("amount", ["-1", "NaN", "Infinity", "1.001"])
def test_invalid_money(client, amount):
    _, _, response = decision(client, amount)
    assert response.status_code == 422
    assert (
        client.post(
            "/api/claims/CLM-1001/payment", json={"thread_id": "test", "amount": amount}
        ).status_code
        == 422
    )


def test_invalid_decisions(client):
    thread, body, _ = decision(client, "1", "refer")
    url = "/api/claims/CLM-1001/decision"
    for change in (
        {"policy_sections": []},
        {"policy_sections": [13]},
        {"manual_sections": [15]},
        {"manual_sections": "nine"},
        {"explanation": ""},
        {"calculation": ""},
        {"outcome": "unknown"},
    ):
        assert client.post(url, json={**body, **change}).status_code == 422
    assert (
        client.post(
            "/api/claims/CLM-1002/decision", json={**body, "payout": "0"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/claims/CLM-1001/payment", json={"thread_id": thread, "amount": "0"}
        ).status_code
        == 409
    )
    assert client.post(url, json={}).status_code == 422
