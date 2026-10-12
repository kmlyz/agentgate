# AgentGate

Deterministic execution boundary and cryptographic audit ledger for LLM tool calls.

## Overview

AgentGate provides a deterministic execution boundary between autonomous agents and mutable systems. It intercepts LLM tool calls at runtime, enforces strict schema validation, stages sensitive mutations into an out-of-band `PENDING_APPROVAL` state, and verifies cryptographic authorization tokens before execution.

## Quickstart

```python
from agentgate.guardrails.adapters.git import CommitProposal, CommitType
from agentgate.runtime import RuntimeGuardrailToolCallback

callback = RuntimeGuardrailToolCallback()

# Intercept runtime tool call via Google ADK callback
receipt = callback.intercept_runtime_tool_call(
    tool="propose_commit",
    args={
        "branch": "main",
        "commit_type": CommitType.FEAT,
        "scope": "core",
        "short_summary": "add execution gate",
    },
)
# Returns:
# {
#   "status": "pending_approval",
#   "proposal_id": "prop_a1b2c3d4",
#   "staged_receipt_id": "rcpt_prop_a1b2c3d4",
#   "state_fingerprint": "...",
#   "message": "PROPOSAL SUBMITTED: ... Staged out-of-band for human operator approval."
# }
```

## CLI Workflow

Operator review, token issuance, and execution:

```bash
# List staged proposals
gate list

# Operator approves proposal out-of-band (returns signed approval token)
gate approve prop_a1b2c3d4

# Execute proposal using the one-time cryptographic token
gate execute prop_a1b2c3d4 --token <approval_token>
```

## Architecture & Security Invariants

- **Physical Role Separation:** The agent MCP server (`agent_mcp`) physically excludes approval and execution tools from its manifest (`tools/list` contains only staging and read-only tools; unexpected calls return `Unknown tool` or `E_PERM`). Administrative controls are isolated to `operator_mcp` and the CLI.
- **Cryptographic Approval Tokens:** Operator approval generates a one-time HMAC-SHA256 token binding `proposal_id`, `payload_sha256`, `state_fingerprint`, and `nonce` with a 30-minute TTL.
- **TOCTOU & State Drift Immunity:** Environmental state fingerprints (`git rev-parse HEAD` and working tree status) are captured at staging. Environment mismatches detected at execution abort with `E_STATE_DRIFT`.
- **Parameter Tampering Protection:** Payload digests are cryptographically verified at execution; modified payloads abort with `E_PAYLOAD_TAMPERED`.
- **AST SQL Inspection (`sqlglot`):** Multi-dialect AST parsing blocks comment injection (`--\nDROP`), tautological filters (`WHERE 1=1`, `WHERE TRUE`, `WHERE 'a'='a'`), and indirect execution (`CALL`, `EXECUTE IMMEDIATE`).
- **Blast-Radius Risk Tiering:**
  - **Tier 0 (Unconstrained):** Read-only inspections, diffs, and test runs. Allowed to execute directly.
  - **Tier 1 (Reversible):** Atomic local file edits with pre-flight rollback checkpoints.
  - **Tier 2 (Hard Gate):** Irreversible Git operations (`push -f`, branch deletions), SQL DDL (`DROP`, `ALTER`, `TRUNCATE`), and unconstrained DML requiring signed human approval.
- **Hash-Chained Audit Ledger:** SHA-256 blocks tracking all proposal lifecycle states (`proposal_created`, `operator_approved`, `mutation_executed`).

## Ecosystem & Integrations

- **Google Agent Development Kit (ADK):** Interception via `before_tool_callback`.
- **Model Context Protocol (MCP):** FastMCP server with separated `agent` and `operator` transport profiles.
- **Pydantic:** Parameter validation via `extra="forbid"` models and deterministic field constraints.
- **sqlglot:** Multi-dialect SQL AST parser and tautology analyzer.

## Verification

The test suite covers schema validation, cryptographic token lifecycle, adversarial SQL injections, and role isolation:

```bash
uv run ruff check .
uv run python -m pytest
```

Status: **281 passing tests**, zero linter warnings.

## AgentGate Pro

For Slack interactive Block Kit dispatchers (HMAC-SHA256 verified) and Cloud Run deployment scaffolding (Terraform / Dockerfile), see `agentgate-pro`.
