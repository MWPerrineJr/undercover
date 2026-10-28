"""The claim agent: one claim, worked from a clean start, reported in a line."""

from decimal import Decimal

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel

from agent import api
from agent.model import model
from agent.tools import tools_for


def report(claim_id: str) -> str:
    """Describe what the run left behind in one line."""
    with api.backend() as client:
        response = client.get(f"/api/claims/{claim_id}")
    response.raise_for_status()
    claim = response.json()
    decision = claim["decision"]
    if not decision:
        return f"{claim_id} failed: no decision saved"
    line = f"{claim_id} {decision['outcome']} ${Decimal(decision['payout']):,.2f}"
    if claim["payment"]:
        return f"{line} paid"
    if claim["status"] == "waiting_for_sign_off":
        return f"{line} waiting for sign-off"
    return line


def work_claim(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Work one claim with a fresh agent and report the outcome."""
    agent = create_agent(
        llm or model(),
        tools=tools_for(claim_id, thread_id),
        system_prompt=api.instructions("claim"),
    )
    agent.invoke(
        {
            "messages": [
                {"role": "user", "content": f"Claim {claim_id}; run {thread_id}"}
            ]
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return report(claim_id)
