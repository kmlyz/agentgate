"""Unit tests verifying physical MCP role separation between agent and operator profiles."""

import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from agentgate.mcp.server import agent_mcp, operator_mcp


def test_agent_mcp_manifest_omits_approval_tools() -> None:
    """Ensure the agent MCP tool manifest physically excludes all approval primitives."""
    agent_tools = [t.name for t in agent_mcp._tool_manager.list_tools()]

    # Approval primitives must NOT exist in the agent session
    assert "approve_proposal" not in agent_tools
    assert "reject_proposal" not in agent_tools
    assert "execute_approved_proposal" not in agent_tools

    # Proposal and read tools MUST be present
    assert "propose_commit" in agent_tools
    assert "propose_branch" in agent_tools
    assert "propose_pr" in agent_tools
    assert "list_pending_proposals" in agent_tools


def test_operator_mcp_manifest_includes_all_tools() -> None:
    """Ensure the operator MCP tool manifest includes administrative approval primitives."""
    operator_tools = [t.name for t in operator_mcp._tool_manager.list_tools()]

    assert "approve_proposal" in operator_tools
    assert "reject_proposal" in operator_tools
    assert "execute_approved_proposal" in operator_tools
    assert "propose_commit" in operator_tools


def test_agent_mcp_call_tool_on_approval_raises_tool_not_found() -> None:
    """Verify calling approve_proposal directly on agent_mcp raises ToolError (not found)."""
    with pytest.raises(ToolError, match="Unknown tool: approve_proposal"):
        asyncio.run(
            agent_mcp.call_tool(
                "approve_proposal",
                {"proposal_id": "prop_test_fake"},
            )
        )
