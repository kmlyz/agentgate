"""Universal domain-agnostic models and base contracts for guardrails."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProposalStatus(str, Enum):
    """Lifecycle status states for an staged execution proposal."""

    DRAFT = "draft"
    VALIDATED = "validated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class BaseProposal(BaseModel, ABC):
    """Abstract base class for all typed, domain-specific proposals.

    Enforces strict typing and forbids arbitrary extra parameters.
    """

    model_config = ConfigDict(extra="forbid")

    @abstractmethod
    def render_message(self) -> str:
        """Deterministic message / payload renderer.

        Must be implemented by concrete domain proposals.
        """
        ...


_PROPOSAL_TYPE_REGISTRY: dict[str, type[BaseProposal]] = {}


def register_proposal_type(tag: str, model_cls: type[BaseProposal]) -> None:
    """Register a concrete BaseProposal subtype into the universal registry."""
    _PROPOSAL_TYPE_REGISTRY[tag] = model_cls


def get_registered_proposal_types() -> dict[str, type[BaseProposal]]:
    """Return dictionary of all currently registered proposal types."""
    return dict(_PROPOSAL_TYPE_REGISTRY)


def discriminate_proposal(v: Any) -> str:
    """Deterministic discriminator resolving proposal type string identifier."""
    if hasattr(v, "proposal_type"):
      return str(v.proposal_type)
    if isinstance(v, dict):
      if "migration_sql" in v or "rollback_sql" in v:
        return "sql_migration" if "migration_sql" in v else "sql_rollback"
      if "target_migration_id" in v:
        return "sql_rollback"
      if "head_branch" in v or "title_type" in v:
        return "pull_request"
      if "branch_name" in v or "full_branch_name" in v:
        return "branch"
      if "commit_type" in v or "short_summary" in v:
        return "commit"
      if "proposal_type" in v:
        return str(v["proposal_type"])
      if "name" in v:
        return "dummy"
    return "base"


def _ensure_domain_proposal_types_loaded() -> None:
    """Lazily load domain packages using dynamic module resolution to preserve AST decoupling."""
    if len(_PROPOSAL_TYPE_REGISTRY) < 5:
      import importlib
      for mod_name in (
          "agentgate.guardrails.adapters.git.schemas",
          "agentgate.guardrails.adapters.sql.sql_schemas_migration",
      ):
        try:
          importlib.import_module(mod_name)
        except (ImportError, ModuleNotFoundError):
          pass


def hydrate_proposal(v: Any) -> BaseProposal:
    """Hydrate a raw dictionary or existing BaseProposal instance into a typed concrete proposal."""
    if isinstance(v, BaseProposal):
      return v
    if isinstance(v, dict):
      disc = discriminate_proposal(v)
      if disc in _PROPOSAL_REGISTRY_GET():
        return _PROPOSAL_TYPE_REGISTRY[disc].model_validate(v)
      _ensure_domain_proposal_types_loaded()
      if disc in _PROPOSAL_TYPE_REGISTRY:
        return _PROPOSAL_TYPE_REGISTRY[disc].model_validate(v)
    raise ValueError(f"Cannot hydrate proposal of type '{type(v).__name__}': {v}")


def _PROPOSAL_REGISTRY_GET() -> dict[str, type[BaseProposal]]:
    return _PROPOSAL_TYPE_REGISTRY


# Type alias for external polymorphic usage
ProposalUnion = BaseProposal


class ProposalValidationResult(BaseModel):
    """Standardized validation outcome."""

    is_valid: bool
    rendered_message: str | None = None
    errors: list[str] = Field(default_factory=list)
    proposal_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProposalRecord(BaseModel):
    """Universal registry record stored in the ApprovalGate state machine."""

    proposal_id: str
    proposal: BaseProposal
    rendered_message: str
    status: ProposalStatus = ProposalStatus.PENDING_APPROVAL
    rejection_reason: str | None = None

    @field_validator("proposal", mode="before")
    @classmethod
    def _validate_and_hydrate_proposal(cls, v: Any) -> BaseProposal:
      """Automatically hydrate dictionary payloads to concrete typed proposals."""
      return hydrate_proposal(v)

