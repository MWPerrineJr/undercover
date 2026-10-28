"""The claim agent's tools: every business read and write goes through the API."""

import json
from urllib.parse import quote

from langchain_core.tools import StructuredTool, tool
from pydantic import BaseModel

from agent import api


class DecisionInput(BaseModel):
    """The structured decision saved for one claim."""

    outcome: str
    payout: str
    calculation: str
    explanation: str
    policy_sections: list[int]
    manual_sections: list[int]


def recorder(claim_id: str, thread_id: str):
    """Return a function that records one step or document read on the claim."""

    def note(client, message: str, kind: str = "step"):
        client.post(
            f"/api/claims/{claim_id}/activity",
            json={"thread_id": thread_id, "message": message, "kind": kind},
        ).raise_for_status()

    return note


def caller(claim_id: str, thread_id: str):
    """Return a function that calls the API and records what it did."""
    note = recorder(claim_id, thread_id)

    def request(method: str, path: str, body: dict | None = None) -> str:
        with api.backend() as client:
            note(client, f"Tool: {method} {path}")
            response = client.request(method, path, json=body)
            note(client, f"Tool result: HTTP {response.status_code}")
            if response.is_error:
                return json.dumps({"error": response.json()["detail"]})
            return response.text

    return request


def record_tools(claim_id: str, thread_id: str, request):
    """Return the tools that read the claim's own records."""

    @tool
    def read_claim() -> str:
        """Read the full assigned claim and all supporting documents."""
        return request("GET", f"/api/claims/{claim_id}")

    @tool
    def read_policy() -> str:
        """Read the assigned claim's policy, trip and add-ons."""
        return request("GET", f"/api/claims/{claim_id}/policy")

    @tool
    def read_customer() -> str:
        """Read the assigned customer's details and earlier claims."""
        return request("GET", f"/api/claims/{claim_id}/customer")

    @tool
    def read_plans() -> str:
        """Read plan limits, deductibles and add-ons."""
        return request("GET", "/api/plans")

    return [read_claim, read_policy, read_customer, read_plans]


def document_tools(claim_id: str, thread_id: str, request):
    """Return the tools that look up the wording and the manual."""
    note = recorder(claim_id, thread_id)

    @tool
    def list_documents() -> str:
        """List the sections of the policy wording and the claims manual."""
        return request("GET", "/api/documents")

    @tool
    def search_documents(query: str) -> str:
        """Find the sections of either document that mention the given words."""
        return request("GET", f"/api/documents/search?q={quote(query)}")

    @tool
    def read_section(document: str, number: int) -> str:
        """Read one numbered section of policy_wording or claims_manual."""
        with api.backend() as client:
            response = client.get(f"/api/documents/{document}/sections/{number}")
            if response.is_error:
                note(client, f"Tool result: HTTP {response.status_code}")
                return json.dumps({"error": response.json()["detail"]})
            section = response.json()
            note(
                client,
                f"Read {section['document_title']} section {number}: "
                f"{section['title']}",
                "read",
            )
        return response.text

    return [list_documents, search_documents, read_section]


def decision_tools(claim_id: str, thread_id: str, request):
    """Return the tools that save the decision and ask for payment."""

    def record_decision(**fields) -> str:
        return request(
            "POST",
            f"/api/claims/{claim_id}/decision",
            {"thread_id": thread_id, **fields},
        )

    @tool
    def pay_claim(amount: str) -> str:
        """Request one simulated payment of the exact approved USD amount."""
        return request(
            "POST",
            f"/api/claims/{claim_id}/payment",
            {"thread_id": thread_id, "amount": amount},
        )

    decision = StructuredTool.from_function(
        func=record_decision,
        name="record_decision",
        description=(
            "Save approve, decline or refer with the USD payout, the arithmetic, "
            "a short explanation and the sections relied on."
        ),
        args_schema=DecisionInput,
    )
    return [decision, pay_claim]


def tools_for(claim_id: str, thread_id: str):
    """Bind every tool to one claim and run, without a handler sign-off tool."""
    request = caller(claim_id, thread_id)
    return [
        *record_tools(claim_id, thread_id, request),
        *document_tools(claim_id, thread_id, request),
        *decision_tools(claim_id, thread_id, request),
    ]
