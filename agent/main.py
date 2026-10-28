"""The UnderCover Agent: all business access goes through the backend API."""

import os

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from agent import api
from agent.tools import tools_for

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"


def model() -> ChatOpenAI:
    """Return the configured OpenRouter model."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def instructions(name: str) -> str:
    """Read one of the backend's instruction texts."""
    with api.backend() as client:
        response = client.get(f"/api/instructions/{name}")
    response.raise_for_status()
    return response.json()["text"]


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    agent = create_agent(
        llm or model(),
        tools=tools_for(claim_id, thread_id),
        system_prompt=instructions("claim"),
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
