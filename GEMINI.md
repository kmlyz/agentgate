# AgentGate: Workspace Constitution (GEMINI.md)

This specification defines the highest-precedence local policies, architectural invariants, and workspace constraints for development within this repository.

## 1. Architectural Axioms & Security
- **Prohibition of Free-Form Text:** Tool calls and agent components must never expose unconstrained string inputs. All parameters must be strictly bounded via `Enum`, regex patterns, and deterministic length constraints.
- **Propose Pattern:** Direct mutating operations (Git commit/push, file deletion, database mutations) are forbidden. Tools must expose `propose_*` interfaces that stage mutations into deterministic intermediate models.
- **Human-in-the-Loop (HITL) Gate:** All destructive or external-facing mutations require transition through an explicit `PENDING_APPROVAL` gate state before execution.

## 2. Workspace Isolation & Nomenclature
- **Strict Notes Isolation:** The `notes/` directory contains private local developer drafts and is strictly out-of-scope. Automated agents must NEVER read, modify, translate, delete, or stage files within `notes/`.
- **Nomenclature Invariants:** The canonical package is `agentgate`. The commercial starter kit is `agentgate-pro` (in prose: "AgentGate Pro"). The legacy words "agent-foundry" and "enterprise" are strictly prohibited across all code, tests, and public docs.
- **Tone & Style:** All public documentation, CLI output, and docstrings must use objective, neutral, zero-fluff systems engineering English (HashiCorp/SQLite style). Promotional or celebratory phrasing is forbidden.

## 3. Engineering & Code Standards
- **Python Ecosystem:** Python 3.12 exclusively; dependency management restricted to Astral `uv` (`uv run`, `uv add`).
- **Frameworks:** Google ADK 2.0 and Model Context Protocol (MCP 2.x).
- **Type Safety:** Strict Pydantic v2 validation (`BaseModel`, `field_validator`, `Field(pattern=...)`, `extra="forbid"`).
- **Verification Invariant:** Code changes must maintain 230 passing tests (`uv run pytest`) and zero linter warnings (`uv run ruff check .`).

## 4. Scoped Naming & Immutability
- **Strict Immutability:** Existing tested code, filenames, and import paths must remain intact and functional.
- **New Files:** Must adhere to the 3-part hierarchy `{root}_{category}_{detail}.py`. Generic filenames (e.g., `utils.py`, `models.py`) are strictly forbidden.
- **New Classes & Functions:** Classes follow `{Detail}{Category}{Root}`; standalone functions follow `{action}_{root}_{category}_{detail}()`.
