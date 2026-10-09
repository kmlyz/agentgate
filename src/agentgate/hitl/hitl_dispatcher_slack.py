"""Slack Block Kit dispatcher generating rich interactive proposal cards with Approve/Reject buttons."""

from typing import Any

import httpx

from agentgate.guardrails.adapters.git import (
    BranchProposal,
    CommitProposal,
    PullRequestProposal,
)
from agentgate.guardrails.adapters.sql import (
    MigrationProposalSql,
    RollbackProposalSql,
)
from agentgate.guardrails.core.models import ProposalRecord


class SlackDispatcherHitl:
    """Builds and dispatches Slack Block Kit cards for Human-in-the-Loop proposal reviews."""

    @classmethod
    def build_proposal_card(cls, record: ProposalRecord) -> dict[str, Any]:
        """Convert a ProposalRecord into a formatted Slack Block Kit payload."""
        prop = record.proposal
        if isinstance(prop, dict):
            # Resolve if serialized
            from agentgate.cli.cli_operator_entrypoint import (
                resolve_proposal_instance,
            )
            prop = resolve_proposal_instance(prop)

        # Categorize kind and details
        if isinstance(prop, BranchProposal):
            kind = "BRANCH CREATION"
            summary_detail = f"*Target Branch:* `{prop.full_branch_name}`\n*Base Branch:* `{prop.base_branch}`"
            code_snippet = None
        elif isinstance(prop, CommitProposal):
            kind = "GIT COMMIT"
            summary_detail = f"*Branch:* `{prop.branch}`\n*Type:* `{prop.commit_type.value}` | *Scope:* `{prop.scope or 'none'}`"
            code_snippet = prop.render_message()
        elif isinstance(prop, PullRequestProposal):
            kind = "PULL REQUEST"
            summary_detail = f"*Route:* `{prop.head_branch}` -> `{prop.base_branch}`\n*Title:* {prop.title}"
            code_snippet = prop.body
        elif isinstance(prop, MigrationProposalSql):
            kind = "SQL MIGRATION"
            summary_detail = f"*Dialect:* `{prop.dialect.value}`\n*Operation:* `{prop.operation_type.value}` on `{prop.target_table}`"
            code_snippet = prop.migration_sql.strip()
        elif isinstance(prop, RollbackProposalSql):
            kind = "SQL ROLLBACK"
            summary_detail = f"*Dialect:* `{prop.dialect.value}`\n*Target Table:* `{prop.target_table}` | *Origin:* `{prop.target_migration_id}`"
            code_snippet = prop.rollback_sql.strip()
        else:
            kind = "PROPOSAL"
            summary_detail = f"*Description:* {record.rendered_message}"
            code_snippet = None

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"AgentGate: {kind} Pending Approval",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Proposal ID:*\n`{record.proposal_id}`"},
                    {"type": "mrkdwn", "text": "*Status:*\n*PENDING_APPROVAL*"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": summary_detail,
                },
            },
        ]

        if code_snippet:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Payload Query / Description:*\n```{code_snippet}```",
                },
            })

        # Interactive action buttons
        blocks.append({
            "type": "actions",
            "block_id": f"actions_{record.proposal_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Approve", "emoji": True},
                    "style": "primary",
                    "action_id": "approve_proposal",
                    "value": record.proposal_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject", "emoji": True},
                    "style": "danger",
                    "action_id": "reject_proposal",
                    "value": record.proposal_id,
                },
            ],
        })

        return {
            "text": f"AgentGate: Proposal {record.proposal_id} requires human approval.",
            "blocks": blocks,
        }

    @classmethod
    def dispatch_webhook(
        cls,
        webhook_url: str,
        record: ProposalRecord,
        timeout: float = 5.0,
    ) -> bool:
        """Post the Block Kit message to a Slack Incoming Webhook URL."""
        payload = cls.build_proposal_card(record)
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(webhook_url, json=payload)
                return resp.status_code == 200
        except httpx.HTTPError:
            return False


# Natural alias
SlackBlockKitDispatcher = SlackDispatcherHitl
