"""Tests verifying granular 3-tier blast-radius risk classification."""

import pytest

from agentgate.guardrails.core import BlastRadiusTier, classify_gate_tier_action


@pytest.mark.parametrize(
    "tool_name",
    [
        "git_status",
        "status",
        "git_log",
        "diff",
        "read_file",
        "list_dir",
        "grep_search",
        "run_tests",
        "inspect_schema",
    ],
)
def test_tier_0_classification(tool_name: str) -> None:
    """Read-only and idempotent inspect tools must be classified as Tier 0."""
    tier = classify_gate_tier_action(tool_name)
    assert tier == BlastRadiusTier.TIER_0_UNCONSTRAINED


@pytest.mark.parametrize(
    "tool_name",
    [
        "write_file",
        "edit_file",
        "replace_file_content",
        "patch_file",
        "create_scratch_file",
    ],
)
def test_tier_1_classification(tool_name: str) -> None:
    """Atomic local file edits must be classified as Tier 1."""
    tier = classify_gate_tier_action(tool_name)
    assert tier == BlastRadiusTier.TIER_1_REVERSIBLE


@pytest.mark.parametrize(
    "tool_name",
    [
        "propose_commit",
        "commit",
        "git_push",
        "git_push_force",
        "delete_branch",
        "propose_sql_migration",
        "sql_migration",
        "execute_approved_proposal",
    ],
)
def test_tier_2_classification(tool_name: str) -> None:
    """Destructive Git and SQL schema alterations must be classified as Tier 2."""
    tier = classify_gate_tier_action(tool_name)
    assert tier == BlastRadiusTier.TIER_2_HARD_GATE


def test_unknown_tool_failsafe_tier_2() -> None:
    """Unrecognized tools must fail-safe into Tier 2 (Hard Gate)."""
    tier = classify_gate_tier_action("completely_unrecognized_custom_action")
    assert tier == BlastRadiusTier.TIER_2_HARD_GATE
