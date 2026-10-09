# Contributing to AgentGate

This specification defines contributor guidelines, quality gate invariants, and validation standards for the AgentGate codebase.

## Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Git CLI

## Environment Setup

1. Synchronize project dependencies:
   ```bash
   uv sync --all-groups
   ```

2. Establish local configuration:
   ```bash
   cp .env.example .env
   ```

## Verification Pipeline

All modifications must pass static linting and the test suite without error or warning prior to submission:

```bash
# Static analysis and style verification
uv run ruff check .

# Test suite execution
uv run pytest tests/
```

## Commit Standards

Commit messages must conform strictly to the Conventional Commits specification:

- `feat:` Introduces new functionality or interfaces.
- `fix:` Corrects a bug or defect.
- `docs:` Documentation modifications exclusively.
- `refactor:` Code restructuring without behavioral mutations.
- `test:` Adds or amends test cases.
- `ci:` Modifies continuous integration pipelines.
- `chore:` Maintenance routines or dependency upgrades.

Invariants:
- Format: `<type>(<scope>): <summary>`
- Imperative mood, lowercase start, maximum 72 characters, no trailing period.
- No model boilerplate phrases (e.g., `ai generated`, `auto-generated`).

## Pull Request Lifecycle

1. Fork or branch from `main`:
   ```bash
   git checkout -b feat/feature-name
   ```
2. Implement focused, atomic changes with minimal diff blast radius.
3. Verify that all 230 unit and security test cases pass locally.
4. Submit pull request utilizing the repository pull request template.
