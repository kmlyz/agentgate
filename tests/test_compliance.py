"""Specification Compliance Suite.

Formally audits AgentGate across 3 official axes:
1. Model Context Protocol (modelcontextprotocol.io) MCP 2.x SDK compliance.
2. Google ADK 2.0 (adk.dev) Coding & Guardrails security contracts.
3. Static Architecture & Portability constraints (AgentGate Core Specification).
"""

import ast
import asyncio
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import (
    JSONRPC_VERSION,
    CallToolResult,
    ErrorData,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    TextContent,
    Tool,
)
from pydantic import ValidationError

from agentgate.guardrails.adapters.git import CommitProposal, CommitType
from agentgate.guardrails.core import (
    ApprovalGate,
    BaseProposal,
    ProposalStatus,
)
from agentgate.mcp.server import approval_gate, mcp


@pytest.fixture(autouse=True)
def reset_approval_gate():
    """Reset the shared approval gate registry before each test."""
    approval_gate.clear()
    yield
    approval_gate.clear()


# ============================================================================
# AXIS 1: Model Context Protocol (MCP 2.x SDK) Standard Compliance
# ============================================================================


class TestMCPProtocolCompliance:
    """Verifies complete adherence to modelcontextprotocol.io specification."""

    def test_tools_list_spec_conformance(self):
        """Audit tools/list: Tool object schema, naming, descriptions, and JSON Schema."""
        tools = asyncio.run(mcp.list_tools())
        assert isinstance(tools, list), "tools/list must return a list of Tool objects."
        assert len(tools) >= 5, "MCPServer must expose all core guardrail tools."

        expected_tools = {
            "propose_commit",
            "list_pending_proposals",
            "approve_proposal",
            "reject_proposal",
            "execute_approved_proposal",
        }
        tool_map = {t.name: t for t in tools}
        missing = expected_tools - set(tool_map.keys())
        assert not missing, f"Missing required MCP tools: {missing}"

        for tool in tools:
            assert isinstance(tool, Tool), f"Item {tool} must be an instance of mcp.types.Tool."
            assert re.match(r"^[a-z0-9_]+$", tool.name), f"Tool name '{tool.name}' must be snake_case."
            assert tool.description and len(tool.description.strip()) > 0, (
                f"Tool '{tool.name}' must provide descriptive documentation."
            )

            # JSON Schema verification (Draft 2020-12 standard)
            schema = tool.input_schema
            assert isinstance(schema, dict), f"Tool '{tool.name}' input_schema must be a dict."
            assert schema.get("type") == "object", f"Tool '{tool.name}' schema root must be 'object'."
            Draft202012Validator.check_schema(schema)

    def test_tools_call_success_structure(self):
        """Audit tools/call: Response structure matches official CallToolResult contract."""
        raw_args = {
            "branch": "main",
            "commit_type": "feat",
            "scope": "compliance",
            "short_summary": "add specification suite",
            "ticket_id": "SPEC-101",
        }
        result = asyncio.run(mcp.call_tool("propose_commit", raw_args))

        assert isinstance(result, CallToolResult), "tools/call must return CallToolResult instance."
        assert result.is_error is False, "Successful execution must set is_error=False."
        assert isinstance(result.content, list) and len(result.content) > 0, (
            "CallToolResult must contain at least one content block."
        )

        content_block = result.content[0]
        assert isinstance(content_block, TextContent), "Tool output content block must be TextContent."
        assert content_block.type == "text"
        assert "PROPOSAL SUBMITTED SUCCESSFULLY" in content_block.text
        assert "feat(compliance): add specification suite [SPEC-101]" in content_block.text
        assert "Status: PENDING_APPROVAL" in content_block.text

    def test_tools_call_error_handling(self):
        """Audit tools/call: Invalid tool name and malformed types raise MCP ToolError."""
        with pytest.raises(ToolError):
            asyncio.run(mcp.call_tool("non_existent_tool_xyz", {}))

        with pytest.raises(ToolError) as exc_info:
            asyncio.run(
                mcp.call_tool(
                    "propose_commit",
                    {
                        "branch": "main",
                        "commit_type": "INVALID_ENUM",
                        "scope": "test",
                        "short_summary": "invalid type",
                    },
                )
            )
        assert "validation error" in str(exc_info.value).lower()

    def test_jsonrpc_2_0_spec_conformance(self):
        """Audit JSON-RPC 2.0 message contracts (version, IDs, and error envelopes)."""
        assert JSONRPC_VERSION == "2.0"

        # Request contract
        request = JSONRPCRequest(jsonrpc=JSONRPC_VERSION, id=42, method="tools/list")
        req_dump = request.model_dump()
        assert req_dump["jsonrpc"] == "2.0"
        assert req_dump["id"] == 42
        assert req_dump["method"] == "tools/list"

        # Response contract
        response = JSONRPCResponse(jsonrpc=JSONRPC_VERSION, id=42, result={"tools": []})
        resp_dump = response.model_dump()
        assert resp_dump["jsonrpc"] == "2.0"
        assert resp_dump["id"] == 42
        assert "result" in resp_dump

        # Error contract
        error_data = ErrorData(code=-32602, message="Invalid params")
        rpc_error = JSONRPCError(jsonrpc=JSONRPC_VERSION, id=42, error=error_data)
        err_dump = rpc_error.model_dump()
        assert err_dump["jsonrpc"] == "2.0"
        assert err_dump["error"]["code"] == -32602
        assert err_dump["error"]["message"] == "Invalid params"


# ============================================================================
# AXIS 2: Google ADK 2.0 (adk.dev) Coding & Guardrails Compliance
# ============================================================================


class TestADKGuardrailCompliance:
    """Verifies adherence to Google ADK 2.0 guidelines and deterministic guardrails."""

    def test_proposal_models_enforce_extra_forbid(self):
        """Audit Pydantic v2 extra='forbid' on all domain proposals to block arbitrary injections."""
        assert BaseProposal.model_config.get("extra") == "forbid"
        assert CommitProposal.model_config.get("extra") == "forbid"

        # Instantiating with arbitrary free-form keys must be rejected deterministically
        with pytest.raises(ValidationError) as exc_info:
            CommitProposal(
                branch="main",
                commit_type=CommitType.FEAT,
                scope="core",
                short_summary="valid summary",
                arbitrary_injected_field="malicious_payload",
            )
        errors = exc_info.value.errors()
        assert any(e["type"] == "extra_forbidden" for e in errors)

    def test_mcp_tools_reject_extra_parameters(self):
        """Audit MCP boundary hardening: Gateway rejects extra parameters at interface boundary."""
        payload_with_extra = {
            "branch": "main",
            "commit_type": "feat",
            "scope": "security",
            "short_summary": "harden gateway",
            "unexpected_parameter": "arbitrary_value",
        }
        with pytest.raises(ToolError) as exc_info:
            asyncio.run(mcp.call_tool("propose_commit", payload_with_extra))
        assert "extra inputs are not permitted" in str(exc_info.value).lower()

    def test_hitl_approval_gate_lifecycle_strictness(self):
        """Audit Human-in-the-Loop state machine: Strict PENDING_APPROVAL -> APPROVED -> EXECUTED."""
        gate = ApprovalGate()
        proposal = CommitProposal(
            branch="main",
            commit_type=CommitType.CHORE,
            scope="ci",
            short_summary="setup test compliance pipeline",
        )

        record = gate.submit_proposal(proposal)
        assert record.status == ProposalStatus.PENDING_APPROVAL

        # Cannot execute while in PENDING_APPROVAL
        with pytest.raises(ValueError, match="without prior APPROVAL"):
            gate.mark_executed(record.proposal_id)

        # Cannot execute while in REJECTED
        reject_gate = ApprovalGate()
        rec_to_reject = reject_gate.submit_proposal(proposal)
        reject_gate.reject(rec_to_reject.proposal_id, reason="Security review failed")
        assert rec_to_reject.status == ProposalStatus.REJECTED

        with pytest.raises(ValueError, match="cannot be approved from status"):
            reject_gate.approve(rec_to_reject.proposal_id)

        with pytest.raises(ValueError, match="without prior APPROVAL"):
            reject_gate.mark_executed(rec_to_reject.proposal_id)

        # Valid lifecycle: PENDING_APPROVAL -> APPROVED -> EXECUTED
        gate.approve(record.proposal_id)
        assert record.status == ProposalStatus.APPROVED
        executed = gate.mark_executed(record.proposal_id)
        assert executed.status == ProposalStatus.EXECUTED

    def test_structured_self_healing_error_format(self):
        """Audit self-healing output: Validation errors must return structured guidance."""
        bad_args = {
            "branch": "main",
            "commit_type": "feat",
            "scope": "INVALID SCOPE WITH UPPERCASE",
            "short_summary": "Fix something. (ai generated)",
        }
        res = asyncio.run(mcp.call_tool("propose_commit", bad_args))
        assert isinstance(res, CallToolResult)
        output_text = res.content[0].text

        assert "REJECTED BY DETERMINISTIC GUARDRAIL:" in output_text
        assert "The proposal violated schema constraints:" in output_text
        assert "Please correct the parameters and propose again." in output_text
        assert "Field 'scope'" in output_text
        assert "Field 'short_summary'" in output_text


# ============================================================================
# AXIS 3: Static Architecture & Portability (AgentGate Core Specification)
# ============================================================================


class TestStaticArchitectureAndPortability:
    """Verifies complete decoupling of core guardrails and portability of codebase."""

    def test_core_module_has_zero_domain_dependencies(self):
        """Audit AST: core/ package must have zero imports referencing domain adapters."""
        core_dir = Path(__file__).resolve().parent.parent / "src" / "agentgate" / "guardrails" / "core"
        assert core_dir.exists() and core_dir.is_dir()

        disallowed_modules = {"adapters", "git", "docker", "wordpress"}

        for py_file in core_dir.glob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top_module = alias.name.split(".")[0]
                        assert top_module not in disallowed_modules, (
                            f"Violation in {py_file.name}: Core module imports disallowed '{alias.name}'"
                        )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    overlap = set(parts) & disallowed_modules
                    assert not overlap, (
                        f"Violation in {py_file.name}: Core module imports disallowed '{node.module}'"
                    )

    def test_zero_absolute_machine_paths(self):
        """Audit portability: src/ must contain zero hardcoded absolute filesystem paths."""
        src_dir = Path(__file__).resolve().parent.parent / "src"
        assert src_dir.exists()

        path_pattern = re.compile(r"(?i)\b[a-z]:[/\\][a-z0-9_.-]+|/(?:home|Users)/[a-z0-9_.-]+")
        violations: list[str] = []

        for py_file in src_dir.rglob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    matches = path_pattern.findall(line)
                    if matches:
                        violations.append(f"{py_file.name}:{line_no} -> {matches}")

        assert len(violations) == 0, f"Found hardcoded absolute machine paths in src/: {violations}"

    def test_zero_hardcoded_secrets(self):
        """Audit security: src/ must contain zero hardcoded credentials, tokens, or API keys."""
        src_dir = Path(__file__).resolve().parent.parent / "src"
        secret_patterns = [
            re.compile(r"AIzaSy[0-9A-Za-z_-]{33}"),       # Google Cloud / AI API keys
            re.compile(r"ghp_[0-9A-Za-z]{36}"),          # GitHub Personal Access Token
            re.compile(r"sk-[0-9A-Za-z]{20,}"),          # OpenAI / generic secret keys
            re.compile(r"AKIA[0-9A-Z]{16}"),             # AWS Access Key ID
        ]
        violations: list[str] = []

        for py_file in src_dir.rglob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    for pattern in secret_patterns:
                        matches = pattern.findall(line)
                        if matches:
                            violations.append(f"{py_file.name}:{line_no} matches {pattern.pattern}")

        assert len(violations) == 0, f"Found potential hardcoded secret patterns in src/: {violations}"
