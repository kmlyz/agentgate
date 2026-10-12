"""Granular 3-tier blast radius risk classifier to prevent operator approval fatigue."""

from enum import Enum
from typing import Any, ClassVar


class BlastRadiusTier(str, Enum):
    """Categorized risk tiers for tool invocations and actions."""

    TIER_0_UNCONSTRAINED = "tier_0_unconstrained"  # Idempotent reads, tests, status
    TIER_1_REVERSIBLE = "tier_1_reversible"        # Local atomic file edits with rollback checkpoints
    TIER_2_HARD_GATE = "tier_2_hard_gate"          # Irreversible Git/SQL schema mutations requiring human approval


class ClassifierTierGate:
    """Classifies actions into deterministic risk tiers based on tool identifier and payload semantics."""

    TIER_0_TOOLS: ClassVar[set[str]] = {
        "status",
        "git_status",
        "log",
        "git_log",
        "diff",
        "git_diff",
        "read",
        "read_file",
        "list_dir",
        "list_files",
        "search",
        "grep_search",
        "run_tests",
        "test",
        "inspect_schema",
        "list_pending_proposals",
    }

    TIER_1_TOOLS: ClassVar[set[str]] = {
        "write_file",
        "edit_file",
        "replace_file_content",
        "patch_file",
        "create_scratch_file",
    }

    TIER_2_TOOLS: ClassVar[set[str]] = {
        "commit",
        "git_commit",
        "propose_commit",
        "create_branch",
        "git_branch",
        "propose_branch",
        "create_pr",
        "git_pr",
        "propose_pr",
        "git_push",
        "git_push_force",
        "push",
        "delete_branch",
        "sql_migration",
        "propose_sql_migration",
        "sql_rollback",
        "propose_sql_rollback",
        "execute_approved_proposal",
        "execute_proposal",
    }

    @classmethod
    def classify_action(
        cls,
        tool_name: str,
        payload: dict[str, Any] | None = None,
    ) -> BlastRadiusTier:
        """Classify a tool call into Tier 0, Tier 1, or Tier 2."""
        normalized = tool_name.strip().lower()

        if normalized in cls.TIER_0_TOOLS:
            return BlastRadiusTier.TIER_0_UNCONSTRAINED

        if normalized in cls.TIER_1_TOOLS:
            return BlastRadiusTier.TIER_1_REVERSIBLE

        if normalized in cls.TIER_2_TOOLS:
            return BlastRadiusTier.TIER_2_HARD_GATE

        # Check payload hints if tool is generic
        if payload:
            if "sql" in payload or "migration_sql" in payload:
                return BlastRadiusTier.TIER_2_HARD_GATE
            if "branch" in payload or "commit_type" in payload:
                return BlastRadiusTier.TIER_2_HARD_GATE

        # Safe default: Unknown tools fail-safe into Tier 2 (Hard Gate)
        return BlastRadiusTier.TIER_2_HARD_GATE


def classify_gate_tier_action(
    tool_name: str,
    payload: dict[str, Any] | None = None,
) -> BlastRadiusTier:
    """Convenience helper to classify action risk tier conforming to hierarchical naming."""
    return ClassifierTierGate.classify_action(tool_name=tool_name, payload=payload)
