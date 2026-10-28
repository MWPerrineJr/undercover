"""The UnderCover Agent: all business access goes through the backend API."""

import json
import os

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=False)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(
        base_url=os.getenv("BACKEND_URL", "http://localhost:8000"), timeout=20
    )


def model() -> ChatOpenAI:
    """Return the configured OpenRouter model."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def tools_for(claim_id: str, thread_id: str):
    """Bind tools to one claim and run, without a handler sign-off tool."""

    def request(method: str, path: str, body: dict):
        with backend() as client:
            client.post(
                f"/api/claims/{claim_id}/activity",
                json={"thread_id": thread_id, "message": f"Tool: {method} {path}"},
            ).raise_for_status()
            response = client.request(
                method, path, json=body if method == "POST" else None
            )
            client.post(
                f"/api/claims/{claim_id}/activity",
                json={
                    "thread_id": thread_id,
                    "message": f"Tool result: HTTP {response.status_code}",
                },
            ).raise_for_status()
            if response.is_error:
                return json.dumps({"error": response.json()["detail"]})
            return response.text

    @tool
    def read_claim() -> str:
        """Read the full assigned claim and all supporting documents."""
        return request("GET", f"/api/claims/{claim_id}", {})

    @tool
    def read_policy() -> str:
        """Read the assigned claim's policy, trip and add-ons."""
        with backend() as client:
            response = client.get(f"/api/claims/{claim_id}")
            response.raise_for_status()
            policy_id = response.json()["policy_id"]
        return request("GET", f"/api/policies/{policy_id}", {})

    @tool
    def read_customer() -> str:
        """Read the assigned customer's details and earlier claims."""
        with backend() as client:
            response = client.get(f"/api/claims/{claim_id}")
            response.raise_for_status()
            customer_id = response.json()["customer_id"]
        return request("GET", f"/api/customers/{customer_id}", {})

    @tool
    def read_plans() -> str:
        """Read plan limits, deductibles and add-ons."""
        return request("GET", "/api/plans", {})

    @tool
    def read_wording() -> str:
        """Read the entire policy wording and its version."""
        return request("GET", "/api/policy-wording", {})

    @tool
    def record_decision(
        outcome: str,
        payout: str,
        calculation: str,
        explanation: str,
        policy_sections: list[int],
    ) -> str:
        """Save approve, decline or refer with USD payout and cited policy sections."""
        return request(
            "POST",
            f"/api/claims/{claim_id}/decision",
            {
                "thread_id": thread_id,
                "outcome": outcome,
                "payout": payout,
                "calculation": calculation,
                "explanation": explanation,
                "policy_sections": policy_sections,
            },
        )

    @tool
    def pay_claim(amount: str) -> str:
        """Request one simulated payment of the exact approved USD amount."""
        return request(
            "POST",
            f"/api/claims/{claim_id}/payment",
            {"thread_id": thread_id, "amount": amount},
        )

    return [
        read_claim,
        read_policy,
        read_customer,
        read_plans,
        read_wording,
        record_decision,
        pay_claim,
    ]


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    with backend() as client:
        response = client.get("/api/instructions")
        response.raise_for_status()
        instructions = response.json()["text"]
    agent = create_agent(
        llm or model(), tools=tools_for(claim_id, thread_id), system_prompt=instructions
    )
    result = agent.invoke(
        {
            "messages": [
                {"role": "user", "content": f"Claim {claim_id}; run {thread_id}"}
            ]
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].text
