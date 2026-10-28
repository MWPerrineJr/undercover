"""The UnderCover Agent: all business access goes through the backend API."""

from langchain_core.language_models import BaseChatModel

from agent.claim import work_claim


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its one-line report."""
    return work_claim(claim_id, thread_id, llm)
