"""Git and Conventional Commits domain schemas."""

from enum import Enum

from pydantic import Field, field_validator

from agentgate.guardrails.core.models import BaseProposal


class CommitType(str, Enum):
    """Conventional Commit type categories."""

    FEAT = "feat"
    FIX = "fix"
    CHORE = "chore"
    DOCS = "docs"
    REFACTOR = "refactor"
    TEST = "test"
    PERF = "perf"


BANNED_PHRASES = (
    "ai generated",
    "model updated",
    "model generated",
    "automated",
    "auto-generated",
    "batch updated",
    "updated files",
    "otomatik",
)


class CommitProposal(BaseProposal):
    """Git commit proposal conforming to Conventional Commits standards.

    Inherits from universal BaseProposal, forbidding free-form text leakage.
    """

    branch: str = Field(
        ...,
        description="Target git branch name.",
        pattern=r"^[a-zA-Z0-9_\-\.\/]+$",
    )
    commit_type: CommitType = Field(
        ...,
        description="Conventional Commit type.",
    )
    scope: str = Field(
        ...,
        description="Scope of changes (max 15 chars, lowercase, no whitespace).",
        pattern=r"^[a-z0-9_\-]{1,15}$",
    )
    short_summary: str = Field(
        ...,
        description="Brief summary in imperative mood, lowercase start, max 50 chars, no trailing period.",
    )
    ticket_id: str | None = Field(
        default=None,
        description="Optional project ticket identifier (e.g. PROJ-123).",
        pattern=r"^[A-Z0-9]+-[0-9]+$",
    )

    @field_validator("short_summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        """Validate commit short summary against Conventional Commits formatting rules."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("short_summary cannot be empty.")
        if len(trimmed) > 50:
            raise ValueError(f"short_summary exceeds 50 characters (current: {len(trimmed)}).")
        if trimmed.endswith("."):
            raise ValueError("short_summary cannot end with a period ('.').")
        if not trimmed[0].islower():
            raise ValueError("short_summary must start with a lowercase letter.")

        lowered = trimmed.lower()
        for banned in BANNED_PHRASES:
            if banned in lowered:
                raise ValueError(f"short_summary contains banned phrasing: '{banned}'.")

        return trimmed

    def render_message(self) -> str:
        """Render deterministic commit message string."""
        base = f"{self.commit_type.value}({self.scope}): {self.short_summary}"
        if self.ticket_id:
            return f"{base} [{self.ticket_id}]"
        return base


class BranchType(str, Enum):
    """Git branch category prefixes."""

    FEAT = "feat"
    FIX = "fix"
    CHORE = "chore"
    DOCS = "docs"
    REFACTOR = "refactor"
    TEST = "test"
    PERF = "perf"


class BranchProposal(BaseProposal):
    """Git branch creation proposal with mandatory prefix enforcement."""

    branch_type: BranchType = Field(
        ...,
        description="Branch category prefix (e.g. feat, fix, chore).",
    )
    branch_name: str = Field(
        ...,
        description="Branch slug without prefix (lowercase alphanumeric and hyphens, max 30 chars).",
        pattern=r"^[a-z0-9][a-z0-9\-]{0,29}$",
    )
    base_branch: str = Field(
        default="main",
        description="Base branch to fork from.",
        pattern=r"^[a-zA-Z0-9_\-\.\/]+$",
    )
    ticket_id: str | None = Field(
        default=None,
        description="Optional project ticket identifier (e.g. PROJ-123).",
        pattern=r"^[A-Z0-9]+-[0-9]+$",
    )

    @property
    def full_branch_name(self) -> str:
        """Compute fully-qualified Git branch name with prefix and optional ticket slug."""
        name = f"{self.branch_type.value}/{self.branch_name}"
        if self.ticket_id:
            return f"{name}-{self.ticket_id.lower()}"
        return name

    def render_message(self) -> str:
        """Render checkout CLI execution string."""
        return f"git checkout -b {self.full_branch_name} {self.base_branch}"


class PullRequestProposal(BaseProposal):
    """Pull request proposal with Conventional Commits title and structured fields."""

    title_type: CommitType = Field(
        ...,
        description="Conventional Commit type for PR title.",
    )
    title_scope: str = Field(
        ...,
        description="Scope of changes (max 15 chars, lowercase, no whitespace).",
        pattern=r"^[a-z0-9_\-]{1,15}$",
    )
    title_summary: str = Field(
        ...,
        description="Brief summary in imperative mood, lowercase start, max 50 chars, no trailing period.",
    )
    head_branch: str = Field(
        ...,
        description="Source head branch name.",
        pattern=r"^[a-zA-Z0-9_\-\.\/]+$",
    )
    base_branch: str = Field(
        default="main",
        description="Target base branch name.",
        pattern=r"^[a-zA-Z0-9_\-\.\/]+$",
    )
    body: str | None = Field(
        default=None,
        description="Optional structured PR description body.",
        max_length=500,
    )
    ticket_id: str | None = Field(
        default=None,
        description="Optional project ticket identifier (e.g. PROJ-123).",
        pattern=r"^[A-Z0-9]+-[0-9]+$",
    )

    @field_validator("title_summary")
    @classmethod
    def validate_title_summary(cls, value: str) -> str:
        """Validate PR title summary against Conventional Commits formatting rules."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("title_summary cannot be empty.")
        if len(trimmed) > 50:
            raise ValueError(f"title_summary exceeds 50 characters (current: {len(trimmed)}).")
        if trimmed.endswith("."):
            raise ValueError("title_summary cannot end with a period ('.').")
        if not trimmed[0].islower():
            raise ValueError("title_summary must start with a lowercase letter.")

        lowered = trimmed.lower()
        for banned in BANNED_PHRASES:
            if banned in lowered:
                raise ValueError(f"title_summary contains banned phrasing: '{banned}'.")

        return trimmed

    def render_title(self) -> str:
        """Render Conventional Commits compliant PR title."""
        base = f"{self.title_type.value}({self.title_scope}): {self.title_summary}"
        if self.ticket_id:
            return f"{base} [{self.ticket_id}]"
        return base

    def render_message(self) -> str:
        """Render PR inspection summary string."""
        return f"PR: '{self.render_title()}' ({self.head_branch} -> {self.base_branch})"


from agentgate.guardrails.core.models import register_proposal_type

register_proposal_type("commit", CommitProposal)
register_proposal_type("branch", BranchProposal)
register_proposal_type("pull_request", PullRequestProposal)
register_proposal_type("pr", PullRequestProposal)

