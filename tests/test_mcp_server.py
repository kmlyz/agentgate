"""Comprehensive tests for Deterministic Guardrails MCPServer.

Verifies strictly-typed proposal tools, reasoning-backed workflow planning,
polymorphic execution and list rendering, and Human-in-the-Loop state machines.
"""

import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from agentgate.guardrails.adapters.git import BranchType, CommitType
from agentgate.guardrails.core import ProposalStatus
from agentgate.mcp.server import (
    approval_gate,
    approve_proposal,
    execute_approved_proposal,
    list_pending_proposals,
    mcp,
    propose_branch,
    propose_commit,
    propose_pr,
    propose_workflow,
    reject_proposal,
    set_reasoning_engine,
)
from agentgate.reasoning import MockReasoningEngine, ReasoningError


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear gate registry and reset reasoning engine before each test."""
    approval_gate.clear()
    set_reasoning_engine(None)
    yield
    approval_gate.clear()
    set_reasoning_engine(None)


# ============================================================================
# 1. Branch Proposals
# ============================================================================


def test_mcp_propose_branch_valid():
    response = propose_branch(
        branch_type=BranchType.FEAT,
        branch_name="oauth2-refresh",
        base_branch="main",
        ticket_id="AUTH-10",
    )
    assert "PROPOSAL SUBMITTED SUCCESSFULLY" in response
    assert "feat/oauth2-refresh-auth-10" in response
    assert "Status: PENDING_APPROVAL" in response


def test_mcp_propose_branch_invalid():
    # Uppercase and invalid characters rejected
    response = propose_branch(
        branch_type=BranchType.FEAT,
        branch_name="INVALID_UPPERCASE",
    )
    assert "REJECTED BY DETERMINISTIC GUARDRAIL" in response
    assert "Field 'branch_name'" in response or "pattern" in response


# ============================================================================
# 2. Commit Proposals
# ============================================================================


def test_mcp_propose_commit_valid():
    response = propose_commit(
        branch="main",
        commit_type=CommitType.FEAT,
        scope="auth",
        short_summary="implement oauth2 refresh",
        ticket_id="AUTH-99",
    )
    assert "PROPOSAL SUBMITTED SUCCESSFULLY" in response
    assert "feat(auth): implement oauth2 refresh [AUTH-99]" in response
    assert "Status: PENDING_APPROVAL" in response


def test_mcp_propose_commit_invalid():
    # Banned phrase and ending with period
    response = propose_commit(
        branch="main",
        commit_type=CommitType.FIX,
        scope="auth",
        short_summary="fix login issue. (ai generated)",
    )
    assert "REJECTED BY DETERMINISTIC GUARDRAIL" in response
    assert "cannot end with a period" in response or "banned phrasing" in response


# ============================================================================
# 3. Pull Request Proposals
# ============================================================================


def test_mcp_propose_pr_valid():
    response = propose_pr(
        title_type=CommitType.FEAT,
        title_scope="auth",
        title_summary="add jwt verification",
        head_branch="feat/auth-jwt",
        base_branch="main",
        ticket_id="AUTH-20",
        body="Includes unit tests.",
    )
    assert "PROPOSAL SUBMITTED SUCCESSFULLY" in response
    assert "feat/auth-jwt -> main" in response
    assert "Status: PENDING_APPROVAL" in response


def test_mcp_propose_pr_invalid():
    # Uppercase summary start and banned phrase
    response = propose_pr(
        title_type=CommitType.FIX,
        title_scope="ui",
        title_summary="Fix button (ai generated)",
        head_branch="fix/btn",
    )
    assert "REJECTED BY DETERMINISTIC GUARDRAIL" in response


# ============================================================================
# 4. Multi-Stage Natural Language Workflow Tool
# ============================================================================


def test_mcp_propose_workflow_with_mock_reasoning():
    mock_spec = {
        "branch_type": "feat",
        "branch_name": "session-store",
        "scope": "session",
        "summary": "implement redis session store",
        "ticket_id": "SESS-100",
        "base_branch": "main",
    }
    set_reasoning_engine(MockReasoningEngine(default_response=mock_spec))

    response = propose_workflow(
        prompt="SESS-100: implement redis session store in session module",
    )

    assert "WORKFLOW PROPOSALS STAGED SUCCESSFULLY" in response
    assert "1. Branch Proposal" in response
    assert "2. Commit Proposal" in response
    assert "3. PR Proposal" in response
    assert "Status: ALL STAGES PENDING_APPROVAL" in response

    # Verify all 3 proposals exist in approval gate
    pending = approval_gate.list_pending()
    assert len(pending) == 3


def test_mcp_propose_workflow_reasoning_failure():
    set_reasoning_engine(MockReasoningEngine(raise_error=ReasoningError("simulated llm failure")))

    response = propose_workflow(prompt="create auth workflow")
    assert "REASONING FAILED" in response
    assert "simulated llm failure" in response


# ============================================================================
# 5. Polymorphic Listing & Approval Lifecycle
# ============================================================================


def test_mcp_list_pending_proposals_polymorphic():
    # Empty
    assert "No pending proposals" in list_pending_proposals()

    # Stage Branch, Commit, and PR
    propose_branch(
        branch_type=BranchType.FEAT,
        branch_name="api-gateway",
    )
    propose_commit(
        branch="feat/api-gateway",
        commit_type=CommitType.FEAT,
        scope="gateway",
        short_summary="add rate limiter",
    )
    propose_pr(
        title_type=CommitType.FEAT,
        title_scope="gateway",
        title_summary="add rate limiter",
        head_branch="feat/api-gateway",
    )

    listed = list_pending_proposals()
    assert "[BRANCH]" in listed
    assert "[COMMIT]" in listed
    assert "[PR]" in listed
    assert "feat/api-gateway" in listed


def test_mcp_approve_proposal():
    res = propose_commit(
        branch="main",
        commit_type=CommitType.DOCS,
        scope="readme",
        short_summary="update quickstart guide",
    )
    prop_id = None
    for line in res.splitlines():
        if line.startswith("Proposal ID:"):
            prop_id = line.split(":", 1)[1].strip()
            break

    assert prop_id is not None
    approval_res = approve_proposal(prop_id)
    assert "PROPOSAL APPROVED" in approval_res
    assert "Status: APPROVED" in approval_res


def test_mcp_reject_proposal():
    res = propose_commit(
        branch="develop",
        commit_type=CommitType.TEST,
        scope="unit",
        short_summary="add mock assertions",
    )
    prop_id = None
    for line in res.splitlines():
        if line.startswith("Proposal ID:"):
            prop_id = line.split(":", 1)[1].strip()
            break

    assert prop_id is not None
    reject_res = reject_proposal(prop_id, reason="Needs more test coverage")
    assert "PROPOSAL REJECTED" in reject_res
    assert "Needs more test coverage" in reject_res


def test_mcp_non_existent_proposal():
    err = approve_proposal("prop_invalid_999")
    assert "was not found" in err


def test_mcp_execution_blocked_without_approval():
    res = propose_commit(
        branch="main",
        commit_type=CommitType.FEAT,
        scope="core",
        short_summary="add test execution gate",
    )
    prop_id = None
    for line in res.splitlines():
        if line.startswith("Proposal ID:"):
            prop_id = line.split(":", 1)[1].strip()
            break

    exec_res = execute_approved_proposal(prop_id)
    assert "EXECUTION BLOCKED (GATEWAY RESTRICTION)" in exec_res


# ============================================================================
# 6. Polymorphic Execution Dispatcher
# ============================================================================


def test_mcp_polymorphic_execution_branch_and_pr():
    # 1. Branch Execution
    b_res = propose_branch(branch_type=BranchType.FEAT, branch_name="poly-branch")
    b_id = next(l.split(":", 1)[1].strip() for l in b_res.splitlines() if l.startswith("Proposal ID:"))

    approve_proposal(b_id)
    exec_b = execute_approved_proposal(b_id, dry_run=True)
    assert "BRANCH CREATION EXECUTED DETERMINISTICALLY" in exec_b
    assert "[DRY_RUN]" in exec_b
    assert approval_gate.get_record(b_id).status == ProposalStatus.EXECUTED

    # 2. PR Execution
    pr_res = propose_pr(
        title_type=CommitType.FEAT,
        title_scope="poly",
        title_summary="add polymorphic test",
        head_branch="feat/poly-branch",
    )
    pr_id = next(l.split(":", 1)[1].strip() for l in pr_res.splitlines() if l.startswith("Proposal ID:"))

    approve_proposal(pr_id)
    exec_pr = execute_approved_proposal(pr_id, dry_run=True)
    assert "PULL REQUEST EXECUTED DETERMINISTICALLY" in exec_pr
    assert "[DRY_RUN]" in exec_pr
    assert approval_gate.get_record(pr_id).status == ProposalStatus.EXECUTED

    # 3. Commit Execution
    c_res = propose_commit(
        branch="feat/poly-branch",
        commit_type=CommitType.FEAT,
        scope="poly",
        short_summary="add polymorphic test commit",
    )
    c_id = next(l.split(":", 1)[1].strip() for l in c_res.splitlines() if l.startswith("Proposal ID:"))

    approve_proposal(c_id)
    exec_c = execute_approved_proposal(c_id, dry_run=True)
    assert "COMMIT EXECUTED DETERMINISTICALLY" in exec_c
    assert "[DRY_RUN]" in exec_c
    assert approval_gate.get_record(c_id).status == ProposalStatus.EXECUTED


# ============================================================================
# 7. MCP JSON-RPC Protocol Hardening & Extra Parameter Rejection
# ============================================================================


def test_mcp_new_tools_reject_extra_parameters():
    # propose_branch rejects extra parameter
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(
            mcp.call_tool(
                "propose_branch",
                {
                    "branch_type": "feat",
                    "branch_name": "safe-branch",
                    "unauthorized_field": "injection",
                },
            )
        )
    assert "extra inputs are not permitted" in str(exc_info.value).lower()

    # propose_pr rejects extra parameter
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(
            mcp.call_tool(
                "propose_pr",
                {
                    "title_type": "feat",
                    "title_scope": "sec",
                    "title_summary": "harden gateway",
                    "head_branch": "feat/sec",
                    "malicious_leak": "payload",
                },
            )
        )
    assert "extra inputs are not permitted" in str(exc_info.value).lower()

    # propose_workflow rejects extra parameter
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(
            mcp.call_tool(
                "propose_workflow",
                {
                    "prompt": "sample prompt",
                    "unexpected_extra": "leak",
                },
            )
        )
    assert "extra inputs are not permitted" in str(exc_info.value).lower()
