# AgentGate

Deterministic execution gate and audit ledger for autonomous agents.

## Scope

AgentGate intercepts tool execution calls from large language models, validating parameters against strict schemas and queueing mutations into an isolated `PENDING_APPROVAL` gate state. Direct host or datastore mutations are blocked until cryptographically verified operator approval is registered.

## Quickstart

```python
from agentgate.guardrails.core import ApprovalGate, ProposalRecord
from agentgate.guardrails.adapters.git import CommitProposal, CommitType

gate = ApprovalGate()
proposal = CommitProposal(branch="main", commit_type=CommitType.FEAT, scope="core", short_summary="add execution gate")
record: ProposalRecord = gate.stage(proposal)

gate.approve(record.proposal_id)
# State transitions: PENDING_APPROVAL -> APPROVED -> EXECUTED
```

## CLI Usage

```bash
gate list
gate approve <id>
gate execute <id>
```

## Ecosystem & Compatibility

AgentGate integrates directly with the modern autonomous agent stack:
- [Google Agent Development Kit (ADK)](https://github.com/google/agent-development-kit): First-class runtime integration via `before_tool_callback`.
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io): Native FastMCP stdio server exposing proposal-and-gate tools.
- [Pydantic v2](https://docs.pydantic.dev): Deterministic boundary validation with `extra="forbid"` schemas and discriminated unions.

## Invariants

- **Strict Schema Enforcement:** All payload models inherit from Pydantic v2 `BaseModel` with `extra="forbid"`. Undefined or unvalidated parameters raise validation errors prior to staging.
- **State Machine Transitions:** State flow enforces `PENDING_APPROVAL` $\rightarrow$ `APPROVED` $\rightarrow$ `EXECUTED` (or `REJECTED`). Unapproved execution attempts abort immediately with an unhandled `ValueError`.
- **$\mathcal{O}(N)$ Lexical SQL Parsing:** Migration payloads are validated using an $\mathcal{O}(N)$ deterministic lexical state machine, isolating literals and multi-line comments without external engine execution.
- **Cryptographic Audit Ledger:** State mutations append SHA-256 hash-chained blocks (`GENESIS` $\rightarrow$ `block_n`), maintaining tamper-evident execution histories.
- **Test Suite Verification:** 230 unit, contract, and adversarial security tests execute with zero failures and zero warnings.

## AgentGate Pro

For Slack interactive approval dispatchers (HMAC-SHA256 verified) and Cloud Run infrastructure scaffolding (Terraform / Dockerfile), see AgentGate Pro (`agentgate-pro`).
