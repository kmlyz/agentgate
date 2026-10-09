"""Strict Pydantic v2 schemas for Webhook and Slack interactive HITL decisions."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WebhookDecisionType(str, Enum):
    """Permitted decision actions for Human-in-the-Loop gates."""

    APPROVE = "approve"
    REJECT = "reject"


class SlackUserHitl(BaseModel):
    """Identity of the Slack operator interacting with the gate."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        pattern=r"^[A-Z0-9]{8,15}$",
        description="Slack User ID (e.g. U0123456789).",
    )
    username: str = Field(
        min_length=2,
        max_length=50,
        pattern=r"^[a-zA-Z0-9._-]+$",
        description="Slack username of the human operator.",
    )


class SlackActionBlockHitl(BaseModel):
    """Button action metadata payload from Slack Block Kit."""

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(
        pattern=r"^(approve|reject)_proposal$",
        description="Identifier of the clicked button.",
    )
    block_id: str | None = Field(
        default=None,
        max_length=100,
        description="Optional block container ID.",
    )
    value: str = Field(
        pattern=r"^prop_[a-f0-9]{8}$",
        description="Target Proposal ID embedded in button value.",
    )
    type: str = Field(
        default="button",
        pattern=r"^button$",
        description="Interactive element type.",
    )


class SlackInteractivePayloadHitl(BaseModel):
    """Structured payload received from Slack interactive webhook callbacks."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(
        default="block_actions",
        pattern=r"^block_actions$",
        description="Slack interaction payload type.",
    )
    user: SlackUserHitl
    actions: list[SlackActionBlockHitl] = Field(
        min_length=1,
        max_length=5,
        description="Array of user triggered actions.",
    )
    response_url: str | None = Field(
        default=None,
        max_length=500,
        description="Temporary webhook URL to update the original Slack message.",
    )
    trigger_id: str | None = Field(
        default=None,
        max_length=120,
        description="Ephemeral trigger ID for modals.",
    )


class WebhookDecisionGenericHitl(BaseModel):
    """Strict typed schema for generic non-Slack external webhook decision payloads."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(
        pattern=r"^prop_[a-f0-9]{8}$",
        description="Target proposal identifier.",
    )
    decision: WebhookDecisionType = Field(
        description="Operator decision: approve or reject.",
    )
    operator_id: str = Field(
        min_length=2,
        max_length=64,
        pattern=r"^[a-zA-Z0-9._@-]+$",
        description="Human operator identifier (email, username, or SSO ID).",
    )
    reason: str = Field(
        min_length=3,
        max_length=500,
        description="Audit rationale explaining the operator's decision.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional audit metadata.",
    )


# Natural naming aliases
SlackUser = SlackUserHitl
SlackActionBlock = SlackActionBlockHitl
SlackInteractivePayload = SlackInteractivePayloadHitl
GenericWebhookDecision = WebhookDecisionGenericHitl
