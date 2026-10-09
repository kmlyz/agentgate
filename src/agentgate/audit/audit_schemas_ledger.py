"""Strict Pydantic v2 schemas for cryptographically immutable audit ledger entries."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

GENESIS_HASH: str = "0" * 64


class AuditEntryType(str, Enum):
    """Categorization of auditable state-machine events."""

    PROPOSAL_CREATED = "proposal_created"
    GUARDRAIL_VALIDATED = "guardrail_validated"
    OPERATOR_APPROVED = "operator_approved"
    OPERATOR_REJECTED = "operator_rejected"
    MUTATION_EXECUTED = "mutation_executed"


def compute_payload_digest(payload: Any) -> str:
    """Compute deterministic SHA-256 digest of arbitrary payload."""
    if isinstance(payload, str):
        serialized = payload
    else:
        serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class LedgerEntryAudit(BaseModel):
    """Cryptographically chained ledger entry forming a tamper-evident audit trail."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
        description="Unique UUIDv4 identifying this ledger record.",
    )
    sequence_number: int = Field(
        ge=0,
        description="Monotonically increasing sequence index starting at 0.",
    )
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="RFC 3339 / ISO 8601 UTC timestamp of creation.",
    )
    proposal_id: str = Field(
        pattern=r"^prop_[a-f0-9]{8}$",
        description="Target proposal identifier.",
    )
    domain: str = Field(
        pattern=r"^(git|sql|core|system)$",
        description="Operational domain prefix.",
    )
    entry_type: AuditEntryType = Field(
        description="State machine transition category.",
    )
    operator_id: str | None = Field(
        default=None,
        max_length=64,
        description="Human operator identifier (email, username, SSO ID).",
    )
    payload_digest: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 digest of the canonical event payload.",
    )
    prev_hash: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 hash of the preceding ledger block (or GENESIS_HASH).",
    )
    current_hash: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="Chained SHA-256 signature sealing this block.",
    )

    @classmethod
    def calculate_block_hash(
        cls,
        sequence_number: int,
        timestamp_utc: str,
        prev_hash: str,
        payload_digest: str,
        entry_type: AuditEntryType,
        proposal_id: str,
        domain: str,
        operator_id: str | None = None,
    ) -> str:
        """Calculate canonical block hash using SHA-256."""
        canonical_content = (
            f"{sequence_number}|{timestamp_utc}|{prev_hash}|"
            f"{payload_digest}|{entry_type.value}|{proposal_id}|{domain}|{operator_id or ''}"
        )
        return hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()

    def verify_block_integrity(self) -> bool:
        """Verify that current_hash matches canonical hash of its contents."""
        expected = self.calculate_block_hash(
            sequence_number=self.sequence_number,
            timestamp_utc=self.timestamp_utc,
            prev_hash=self.prev_hash,
            payload_digest=self.payload_digest,
            entry_type=self.entry_type,
            proposal_id=self.proposal_id,
            domain=self.domain,
            operator_id=self.operator_id,
        )
        return self.current_hash == expected


# Natural alias
LedgerEntry = LedgerEntryAudit
