"""Git Domain Guardrail Adapter implementation."""

import os
import subprocess
from typing import Any

from pydantic import ValidationError

from agentgate.guardrails.adapters.git.schemas import (
    BranchProposal,
    CommitProposal,
    PullRequestProposal,
)
from agentgate.guardrails.core.adapter import BaseGuardrailAdapter
from agentgate.guardrails.core.models import (
    ProposalRecord,
    ProposalValidationResult,
)

DEFAULT_GIT_TIMEOUT: float = 30.0


class GitExecutionError(Exception):
    """Structured exception representing a Git execution failure or timeout."""

    def __init__(
        self,
        message: str,
        returncode: int | None = None,
        command: list[str] | None = None,
        is_timeout: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.returncode = returncode
        self.command = command
        self.is_timeout = is_timeout


def _build_git_env() -> dict[str, str]:
    """Construct non-interactive environment for Git and GitHub CLI execution."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GH_NO_PROMPT"] = "1"
    return env


def _run_git_subprocess(
    cmd: list[str],
    cwd: str,
    timeout: float = DEFAULT_GIT_TIMEOUT,
) -> tuple[bool, str]:
    """Execute Git or GitHub CLI command with strict timeout and prompt suppression."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=_build_git_env(),
        )
        if result.returncode != 0:
            err = result.stderr.strip() or result.stdout.strip()
            return False, f"Git execution failed (Exit code {result.returncode}): {err}"
        return True, result.stdout.strip()
    except subprocess.TimeoutExpired as exc:
        err_msg = f"Git command timed out after {exc.timeout}s: {' '.join(cmd)}"
        return False, f"GitExecutionError: {err_msg}"
    except OSError as exc:
        err_msg = f"Failed to invoke Git command: {exc}"
        return False, f"GitExecutionError: {err_msg}"


class GitGuardrailAdapter(BaseGuardrailAdapter):
    """Adapter enforcing Conventional Commits and safe Git execution."""

    @property
    def domain(self) -> str:
        """Domain identifier string."""
        return "git"

    def validate_payload(self, raw_data: dict[str, Any]) -> ProposalValidationResult:
        """Validate raw commit payload against CommitProposal schema."""
        try:
            proposal = CommitProposal.model_validate(raw_data)
            rendered = proposal.render_message()
            return ProposalValidationResult(
                is_valid=True,
                rendered_message=rendered,
                errors=[],
                metadata={"domain": self.domain, "branch": proposal.branch},
            )
        except ValidationError as exc:
            error_messages = []
            for err in exc.errors():
                loc = ".".join(str(item) for item in err.get("loc", []))
                msg = err.get("msg", "Validation error")
                error_messages.append(f"Field '{loc}': {msg}")
            return ProposalValidationResult(
                is_valid=False,
                rendered_message=None,
                errors=error_messages,
                metadata={"domain": self.domain},
            )

    def parse_proposal(self, raw_data: dict[str, Any]) -> CommitProposal:
        """Parse raw dictionary into validated CommitProposal instance."""
        return CommitProposal.model_validate(raw_data)

    def validate_branch_payload(self, raw_data: dict[str, Any]) -> ProposalValidationResult:
        """Validate branch creation payload against strict naming rules."""
        try:
            proposal = BranchProposal.model_validate(raw_data)
            rendered = proposal.render_message()
            return ProposalValidationResult(
                is_valid=True,
                rendered_message=rendered,
                errors=[],
                metadata={
                    "domain": self.domain,
                    "action": "create_branch",
                    "branch": proposal.full_branch_name,
                },
            )
        except ValidationError as exc:
            error_messages = []
            for err in exc.errors():
                loc = ".".join(str(item) for item in err.get("loc", []))
                msg = err.get("msg", "Validation error")
                error_messages.append(f"Field '{loc}': {msg}")
            return ProposalValidationResult(
                is_valid=False,
                rendered_message=None,
                errors=error_messages,
                metadata={"domain": self.domain, "action": "create_branch"},
            )

    def parse_branch_proposal(self, raw_data: dict[str, Any]) -> BranchProposal:
        """Parse raw dictionary into validated BranchProposal instance."""
        return BranchProposal.model_validate(raw_data)

    def validate_pr_payload(self, raw_data: dict[str, Any]) -> ProposalValidationResult:
        """Validate pull request payload against Conventional Commits title rules."""
        try:
            proposal = PullRequestProposal.model_validate(raw_data)
            rendered = proposal.render_message()
            return ProposalValidationResult(
                is_valid=True,
                rendered_message=rendered,
                errors=[],
                metadata={
                    "domain": self.domain,
                    "action": "create_pr",
                    "title": proposal.render_title(),
                },
            )
        except ValidationError as exc:
            error_messages = []
            for err in exc.errors():
                loc = ".".join(str(item) for item in err.get("loc", []))
                msg = err.get("msg", "Validation error")
                error_messages.append(f"Field '{loc}': {msg}")
            return ProposalValidationResult(
                is_valid=False,
                rendered_message=None,
                errors=error_messages,
                metadata={"domain": self.domain, "action": "create_pr"},
            )

    def parse_pr_proposal(self, raw_data: dict[str, Any]) -> PullRequestProposal:
        return PullRequestProposal.model_validate(raw_data)

    @staticmethod
    def execute_commit(
        record: ProposalRecord,
        repo_path: str = ".",
        dry_run: bool = False,
        timeout: float = DEFAULT_GIT_TIMEOUT,
    ) -> tuple[bool, str]:
        """Execute git commit deterministically with approved rendered message."""
        if dry_run:
            return True, f"[DRY_RUN] Committed message: '{record.rendered_message}'"
        cmd = ["git", "commit", "-m", record.rendered_message]
        return _run_git_subprocess(cmd, cwd=repo_path, timeout=timeout)

    @staticmethod
    def execute_create_branch(
        record: ProposalRecord,
        repo_path: str = ".",
        dry_run: bool = False,
        timeout: float = DEFAULT_GIT_TIMEOUT,
    ) -> tuple[bool, str]:
        """Execute git branch creation deterministically."""
        proposal = record.proposal
        if isinstance(proposal, dict):
            proposal = BranchProposal.model_validate(proposal)
        branch_name = (
            proposal.full_branch_name
            if hasattr(proposal, "full_branch_name")
            else str(proposal)
        )
        base_branch = getattr(proposal, "base_branch", "main")

        if dry_run:
            return True, f"[DRY_RUN] Branch created: {branch_name} from {base_branch}"

        cmd = ["git", "checkout", "-b", branch_name, base_branch]
        ok, out = _run_git_subprocess(cmd, cwd=repo_path, timeout=timeout)
        if ok and not out:
            out = f"Switched to a new branch '{branch_name}'"
        return ok, out

    @staticmethod
    def execute_create_pr(
        record: ProposalRecord,
        repo_path: str = ".",
        dry_run: bool = False,
        timeout: float = DEFAULT_GIT_TIMEOUT,
    ) -> tuple[bool, str]:
        """Execute GitHub PR proposal deterministically."""
        proposal = record.proposal
        if isinstance(proposal, dict):
            proposal = PullRequestProposal.model_validate(proposal)
        title = (
            proposal.render_title()
            if hasattr(proposal, "render_title")
            else record.rendered_message
        )
        head_branch = getattr(proposal, "head_branch", "HEAD")
        base_branch = getattr(proposal, "base_branch", "main")
        body = getattr(proposal, "body", "") or ""

        if dry_run:
            return True, f"[DRY_RUN] Pull Request created: '{title}' ({head_branch} -> {base_branch})"

        cmd = [
            "gh",
            "pr",
            "create",
            "--title",
            title,
            "--base",
            base_branch,
            "--head",
            head_branch,
        ]
        if body:
            cmd.extend(["--body", body])
        return _run_git_subprocess(cmd, cwd=repo_path, timeout=timeout)



class GitProposalValidator:
    """Convenience validator class maintaining backward-compatibility."""

    @staticmethod
    def validate_proposal_dict(data: dict[str, Any]) -> ProposalValidationResult:
        """Validate proposal dictionary using default GitGuardrailAdapter."""
        adapter = GitGuardrailAdapter()
        return adapter.validate_payload(data)
