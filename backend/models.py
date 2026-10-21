"""Business records and API inputs."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(ge=0, decimal_places=2, allow_inf_nan=False)]
Text = Annotated[str, Field(min_length=1)]


class Record(BaseModel):
    """Retain every source field alongside typed relationship identifiers."""

    model_config = ConfigDict(extra="allow")


class Customer(Record):
    customer_id: str
    name: str
    previous_claims: list[dict]


class Policy(Record):
    policy_id: str
    customer_id: str
    plan: str
    add_ons: list[str]


class Handler(Record):
    handler_id: str
    name: str
    can_approve_over_limit: bool


class Claim(Record):
    claim_id: str
    policy_id: str
    customer_id: str
    claim_type: str
    story: str
    items: list[dict]
    documents: list[dict]
    amount_claimed: Money


class Decision(BaseModel):
    thread_id: Text
    outcome: Literal["approve", "decline", "refer"]
    payout: Money
    calculation: Text
    explanation: Text
    policy_sections: Annotated[
        list[Annotated[int, Field(ge=1, le=12)]], Field(min_length=1)
    ]

    @model_validator(mode="after")
    def non_approval_payout(self):
        """Only approved decisions can have a payout."""
        if self.outcome != "approve" and self.payout != 0:
            raise ValueError("Declined and referred claims must have zero payout")
        return self


class SignOff(BaseModel):
    thread_id: Text
    handler_id: Text


class Payment(BaseModel):
    thread_id: Text
    amount: Money


class Activity(BaseModel):
    thread_id: Text
    message: Annotated[str, Field(min_length=1, max_length=300)]
