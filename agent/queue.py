"""The queue agent: it plans the run, delegates each claim and reports back."""

import json

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool

from agent import api
from agent.claim import work_claim
from agent.model import model


def caller(run_id: str):
    """Return a function that calls the run's part of the API."""

    def request(method: str, path: str, body: dict | None = None) -> str:
        with api.backend() as client:
            response = client.request(method, f"/api/queue/{run_id}{path}", json=body)
        if response.is_error:
            return json.dumps({"error": response.json()["detail"]})
        return response.text

    return request


def planning_tools(request):
    """Return the tools that plan and track the run."""

    @tool
    def list_waiting_claims() -> str:
        """List the waiting claims and how many you may still work."""
        return request("GET", "/waiting")

    @tool
    def set_todo_list(items: list[dict]) -> str:
        """Set the to-do list from claim_id and title pairs, in working order."""
        return request("POST", "/todos", {"items": items})

    @tool
    def update_todo(claim_id: str, state: str, note: str) -> str:
        """Mark an item to_do, in_progress, done or left_for_handler, with a note."""
        return request("POST", f"/todos/{claim_id}", {"state": state, "note": note})

    @tool
    def finish_run(summary: str) -> str:
        """Close the run with a short summary for the handlers."""
        return request("POST", "/finish", {"summary": summary})

    return [list_waiting_claims, set_todo_list, update_todo, finish_run]


def working_tool(request, worker):
    """Return the tool that hands one claim to a fresh claim agent."""

    @tool
    def work_one_claim(claim_id: str) -> str:
        """Give one claim to a fresh claim agent and return its one-line report."""
        started = json.loads(request("POST", f"/claims/{claim_id}/start"))
        if "error" in started:
            return f"{claim_id} not worked: {started['error']}"
        thread_id = started["thread_id"]
        try:
            report = worker(claim_id, thread_id)
        except Exception as failure:
            report = f"{claim_id} failed: {type(failure).__name__}"
        finished = json.loads(
            request(
                "POST",
                f"/claims/{claim_id}/finish",
                {"thread_id": thread_id, "report": report},
            )
        )
        if finished.get("left_for_handler"):
            return f"{report}; left for a handler after two attempts"
        return report

    return [work_one_claim]


def run_queue(run_id: str, llm: BaseChatModel | None = None, worker=None) -> str:
    """Work the queue for one run and return the agent's closing reply."""
    request = caller(run_id)
    agent = create_agent(
        llm or model(),
        tools=[*planning_tools(request), *working_tool(request, worker or work_claim)],
        system_prompt=api.instructions("queue"),
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Work the queue; run {run_id}"}]},
        config={"configurable": {"thread_id": run_id}},
    )
    return result["messages"][-1].text
