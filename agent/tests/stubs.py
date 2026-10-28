"""Scripted tool calls shared by unit and browser tests; no model API calls."""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import Field


class StubModel(GenericFakeChatModel):
    """Emit scripted tool calls in place of a remote model, keeping what it saw."""

    seen: list = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, *args, **kwargs):
        self.seen.append(messages)
        return super()._generate(messages, *args, **kwargs)


def scripted(outcome="approve", amount="420.00", attempt_payment=True):
    calls = [
        (name, {})
        for name in ("read_claim", "read_policy", "read_customer", "read_plans")
    ]
    calls.append(("list_documents", {}))
    calls.append(("search_documents", {"query": "baggage delay"}))
    calls.append(("read_section", {"document": "policy_wording", "number": 3}))
    calls.append(("read_section", {"document": "claims_manual", "number": 9}))
    calls.append(
        (
            "record_decision",
            {
                "outcome": outcome,
                "payout": amount,
                "calculation": f"Synthetic fixture: eligible USD {amount}; no offsets.",
                "explanation": "Synthetic decision. See section 3.",
                "policy_sections": [3, 10],
                "manual_sections": [9],
            },
        )
    )
    if attempt_payment:
        calls.append(("pay_claim", {"amount": amount}))
    replies = [
        AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": str(i)}])
        for i, (name, args) in enumerate(calls)
    ]
    replies.append(AIMessage(content="Claim processing complete."))
    return StubModel(messages=iter(replies))


def queue_script(claim_ids, cap_note="worked"):
    """Script a queue agent that plans, works each claim and closes the run."""
    calls = [("list_waiting_claims", {})]
    calls.append(
        (
            "set_todo_list",
            {
                "items": [
                    {"claim_id": claim_id, "title": f"Work {claim_id}"}
                    for claim_id in claim_ids
                ]
            },
        )
    )
    for claim_id in claim_ids:
        calls.append(
            ("update_todo", {"claim_id": claim_id, "state": "in_progress", "note": ""})
        )
        calls.append(("work_one_claim", {"claim_id": claim_id}))
        calls.append(
            (
                "update_todo",
                {
                    "claim_id": claim_id,
                    "state": "done",
                    "note": f"{claim_id} {cap_note}",
                },
            )
        )
    calls.append(("list_waiting_claims", {}))
    calls.append(("finish_run", {"summary": f"Worked {len(claim_ids)} claims."}))
    replies = [
        AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": str(i)}])
        for i, (name, args) in enumerate(calls)
    ]
    replies.append(AIMessage(content="Queue run complete."))
    return StubModel(messages=iter(replies))
