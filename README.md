# AgentGate

Deterministic execution gate and audit ledger for LLM tool calls.

## Overview

AgentGate intercepts LLM tool calls, validates parameters against strict schemas, and stages mutations into a `PENDING_APPROVAL` state. Direct host or datastore operations are blocked until operator approval is recorded.

## Quickstart

```python
from agentgate.guardrails.core import ApprovalGate, ProposalRecord
from agentgate.guardrails.adapters.git import CommitProposal, CommitType

gate = ApprovalGate()
proposal = CommitProposal(branch="main", commit_type=CommitType.FEAT, scope="core", short_summary="add execution gate")
record: ProposalRecord = gate.stage(proposal)

gate.approve(record.proposal_id)
# Lifecycle: PENDING_APPROVAL -> APPROVED -> EXECUTED
```

## CLI Usage

```bash
gate list
gate approve <id>
gate execute <id>
```

## Ecosystem

- [Google Agent Development Kit (ADK)](https://adk.dev/): Interception via `before_tool_callback`.
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io): FastMCP stdio server for proposal staging and execution.
- [Pydantic v2](https://docs.pydantic.dev): Parameter validation via `extra="forbid"` models and discriminated unions.

## Core Invariants

- **Schema Enforcement:** Payload models inherit from Pydantic v2 `BaseModel` with `extra="forbid"`. Unrecognized parameters fail validation prior to staging.
- **State Machine:** Transitions enforce `PENDING_APPROVAL` $\rightarrow$ `APPROVED` $\rightarrow$ `EXECUTED` (or `REJECTED`). Unapproved execution attempts abort with `ValueError`.
- **Lexical SQL Scanner:** $\mathcal{O}(N)$ single-pass parser analyzes migration statements and isolates literals/comments without database execution.
- **Audit Ledger:** SHA-256 hash-chained blocks (`GENESIS` $\rightarrow$ `block_n`) record all state mutations.
- **Verification:** 230 unit, contract, and adversarial security tests.

## AgentGate Pro

For Slack interactive approval dispatchers (HMAC-SHA256 verified) and Cloud Run infrastructure scaffolding (Terraform / Dockerfile), see AgentGate Pro (`agentgate-pro`).
