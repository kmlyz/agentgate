# Verified GitHub Agent Blueprint

Deterministic Git and GitHub execution guardrails with Human-in-the-Loop (HITL) approval gates.

Intercepts LLM tool calls to prevent arbitrary commits, unauthorized branch mutations, or malformed pull requests by binding all side-effecting operations to strictly-typed Pydantic v2 schemas and the `ApprovalGate` state machine.

---

## Key Capabilities

1. **Deterministic Branch Guardrails:**
   - Enforces standardized branch naming schemes (`feat/`, `fix/`, `chore/`, `docs/`, `refactor/`, `test/`, `perf/`).
   - Forbids unconstrained strings, uppercase letters, spaces, and arbitrary naming.

2. **Conventional Commits Enforcement:**
   - Validates imperative mood, lowercase headers, maximum character constraints, and ticket tracking identifiers (`PROJ-123`).
   - Rejects banned phrases and probabilistic model jargon (e.g. `ai generated`, `updated files`).

3. **Structured Pull Requests:**
   - Deterministically generates standardized PR titles derived from validated commit metadata.
   - Enforces target base branch mapping and structured bodies.

4. **Human-in-the-Loop (HITL) State Machine:**
   - No mutating Git command (`git checkout -b`, `git commit`, `gh pr create`) executes without prior authorization.
   - State transition: `PENDING_APPROVAL` -> `APPROVED` -> `EXECUTED`.

---

## Architecture Overview

```text
TaskSpecification (Validated Input)
       │
       ▼
VerifiedGitHubAgent.plan_workflow()
       ├── 1. BranchProposal      ──► [ApprovalGate: PENDING_APPROVAL]
       ├── 2. CommitProposal      ──► [ApprovalGate: PENDING_APPROVAL]
       └── 3. PullRequestProposal ──► [ApprovalGate: PENDING_APPROVAL]
                                                │
                                       Human Authorization
                                                │
                                                ▼
VerifiedGitHubAgent.execute_proposal() ──► Deterministic Execution
```

---

## Installation & Setup

### Requirements
- Python `>=3.12`
- `uv` package manager
- Git CLI (and optionally GitHub CLI `gh`)

### Installation
From the root of your project:
```bash
uv sync --all-groups
```

### Configuration
Copy the sample environment file:
```bash
cp .env.example .env
```

Set your credentials in `.env`:
```ini
GITHUB_TOKEN=ghp_your_personal_access_token
GITHUB_REPOSITORY=owner/repository
TARGET_BRANCH=main
```

---

## Usage Example

### Python API

```python
from blueprints.verified_github_agent import TaskSpecification, VerifiedGitHubAgent
from agentgate.guardrails.adapters.git import BranchType
from agentgate.guardrails.core import ApprovalGate

# 1. Initialize gate and agent
gate = ApprovalGate()
agent = VerifiedGitHubAgent(approval_gate=gate)

# 2. Define a strictly-typed task (can be produced by an LLM)
task = TaskSpecification(
    branch_type=BranchType.FEAT,
    branch_name="auth-oauth2",
    scope="auth",
    summary="implement oauth2 refresh token handler",
    ticket_id="AUTH-101",
    base_branch="main",
)

# 3. Plan workflow (creates proposals in PENDING_APPROVAL state)
proposals = agent.plan_workflow(task)
for prop in proposals:
    print(f"[{prop.proposal_id}] Status: {prop.status} | {prop.rendered_message}")

# 4. Operator authorizes a proposal
branch_prop_id = proposals[0].proposal_id
gate.approve(branch_prop_id)

# 5. Deterministic execution
success, output = agent.execute_proposal(branch_prop_id, dry_run=True)
print(f"Executed: {success} -> {output}")
```

### Natural Language Planning with Gemini Reasoning

```python
from blueprints.verified_github_agent import VerifiedGitHubAgent
from agentgate.reasoning import GeminiReasoningEngine

# 1. Initialize with Gemini Reasoning Engine (uses gemini-3.8-flash & structured outputs)
engine = GeminiReasoningEngine()
agent = VerifiedGitHubAgent(reasoning_engine=engine)

# 2. Plan workflow directly from a natural language requirement
task_spec, proposals = agent.plan_from_natural_language(
    "AUTH-101: implement oauth2 refresh token handler for auth module",
    base_branch="main",
)

# 3. Proposals are staged in PENDING_APPROVAL state, ready for human authorization
for prop in proposals:
    print(f"[{prop.proposal_id}] Status: {prop.status} | {prop.rendered_message}")
```

---

## Google ADK 2.0 & Cloud Run Runtime

### Running with Google ADK `root_agent`

The blueprint exports a configured `root_agent` connected directly to the AgentGate `RuntimeGuardrailToolCallback`:

```python
from blueprints.verified_github_agent import root_agent

# The agent is pre-configured with gemini-3.8-flash and safe proposal tools:
print(root_agent.name)        # "verified_github_agent"
print(root_agent.model)       # "gemini-3.8-flash"
print(root_agent.tools)       # [propose_branch, propose_commit, propose_pr, ...]
```

All tool calls made by `root_agent` are intercepted by `before_tool_callback`. Proposals are validated against Pydantic schemas and placed in `PENDING_APPROVAL` status inside `ApprovalGate`. Direct mutations are rejected unless an approved `proposal_id` is provided.

---

## Cloud Run & Google Agents CLI Deployment

### Local Development Server

Run the ADK server locally:
```bash
uv run python -m google.adk.server --host 0.0.0.0 --port 8080 blueprints.verified_github_agent.github_agent_runtime
```

### Google Agents CLI Validation

Inspect and validate the manifest:
```bash
agents-cli info
```

### Cloud Run Container Build & Run

Build the container image:
```bash
docker build -t verified-github-agent:latest -f blueprints/verified_github_agent/Dockerfile .
```

Run locally:
```bash
docker run -p 8080:8080 -e PORT=8080 -e GEMINI_API_KEY=$GEMINI_API_KEY verified-github-agent:latest
```

---

## Schema Contracts

All schemas inherit from `BaseProposal` and enforce Pydantic v2 `extra="forbid"`, preventing unauthorized payload injection:

- `BranchProposal`: Category prefix (`BranchType`), regex-validated slug, base branch, and optional ticket ID.
- `CommitProposal`: Conventional Commit type (`CommitType`), scope regex, imperative summary validator, and optional ticket ID.
- `PullRequestProposal`: Structured title components, head branch, target base branch, and optional body.

---

## Verification & Testing

Run blueprint unit, runtime integration, and compliance tests:
```bash
uv run pytest tests/test_verified_github_agent.py tests/test_verified_github_agent_runtime.py -v
```

