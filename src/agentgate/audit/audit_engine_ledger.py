"""Cryptographically chained tamper-evident audit ledger engine with atomic disk persistence."""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentgate.audit.audit_schemas_ledger import (
    GENESIS_HASH,
    AuditEntryType,
    LedgerEntryAudit,
    compute_payload_digest,
)

DEFAULT_LEDGER_STORAGE_PATH: Path = Path(".tmp/guardrail_audit_ledger.json")


class LedgerEngineAudit:
    """Manages an immutable, append-only, hash-chained ledger verifying complete state transitions."""

    def __init__(self, storage_path: Path | str | None = DEFAULT_LEDGER_STORAGE_PATH) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        self._chain: list[LedgerEntryAudit] = []
        if self._storage_path:
            self._load_from_disk()

    @property
    def chain(self) -> list[LedgerEntryAudit]:
        """Read-only view of the current audit chain."""
        return list(self._chain)

    def append_event(
        self,
        proposal_id: str,
        domain: str,
        entry_type: AuditEntryType | str,
        payload: Any,
        operator_id: str | None = None,
    ) -> LedgerEntryAudit:
        """Seal and append a new event block into the cryptographic hash chain."""
        resolved_type = AuditEntryType(entry_type) if isinstance(entry_type, str) else entry_type
        sequence_number = len(self._chain)
        prev_hash = self._chain[-1].current_hash if self._chain else GENESIS_HASH
        payload_digest = compute_payload_digest(payload)
        timestamp_utc = datetime.now(UTC).isoformat()

        current_hash = LedgerEntryAudit.calculate_block_hash(
            sequence_number=sequence_number,
            timestamp_utc=timestamp_utc,
            prev_hash=prev_hash,
            payload_digest=payload_digest,
            entry_type=resolved_type,
            proposal_id=proposal_id,
            domain=domain,
            operator_id=operator_id,
        )

        entry = LedgerEntryAudit(
            sequence_number=sequence_number,
            timestamp_utc=timestamp_utc,
            proposal_id=proposal_id,
            domain=domain,
            entry_type=resolved_type,
            operator_id=operator_id,
            payload_digest=payload_digest,
            prev_hash=prev_hash,
            current_hash=current_hash,
        )

        self._chain.append(entry)
        self._save_to_disk()
        return entry

    def verify_integrity(self) -> tuple[bool, str | None]:
        """Verify the complete hash chain from Genesis block forward.

        Returns:
            Tuple of (is_valid, error_reason).
        """
        if not self._chain:
            return True, None

        for idx, entry in enumerate(self._chain):
            # 1. Verify sequence order
            if entry.sequence_number != idx:
                return (
                    False,
                    (
                        f"Tamper detected: Sequence number mismatch at index {idx} "
                        f"(expected {idx}, got {entry.sequence_number})."
                    ),
                )

            # 2. Verify genesis or link to previous block
            if idx == 0:
                if entry.prev_hash != GENESIS_HASH:
                    return (
                        False,
                        "Tamper detected: Genesis block prev_hash corrupted at index 0.",
                    )
            else:
                preceding = self._chain[idx - 1]
                if entry.prev_hash != preceding.current_hash:
                    return (
                        False,
                        (
                            f"Tamper detected: Hash chain broken at block {idx}. "
                            f"Expected prev_hash '{preceding.current_hash}', got '{entry.prev_hash}'."
                        ),
                    )

            # 3. Verify internal block hash integrity
            if not entry.verify_block_integrity():
                return (
                    False,
                    (
                        f"Tamper detected: Block payload or metadata modified at block {idx} "
                        f"(hash mismatch for proposal '{entry.proposal_id}')."
                    ),
                )

        return True, None

    def export_audit_trail(self, proposal_id: str) -> list[LedgerEntryAudit]:
        """Export all chronological ledger blocks associated with a specific proposal."""
        return [b for b in self._chain if b.proposal_id == proposal_id]

    def clear(self) -> None:
        """Clear in-memory ledger and remove persisted file (used for isolated test fixtures)."""
        self._chain.clear()
        if self._storage_path and self._storage_path.exists():
            self._storage_path.unlink()

    def _save_to_disk(self) -> None:
        """Atomically persist ledger blocks to disk in valid JSON format."""
        if not self._storage_path:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        serialized_entries = [entry.model_dump() for entry in self._chain]

        # Atomic write via temporary file
        temp_dir = self._storage_path.parent
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            json.dump(serialized_entries, tf, indent=2)
            temp_name = tf.name

        Path(temp_name).replace(self._storage_path)

    def _load_from_disk(self) -> None:
        """Load persisted ledger entries from disk."""
        if not self._storage_path or not self._storage_path.exists():
            return

        try:
            with open(self._storage_path, encoding="utf-8") as f:
                raw_entries = json.load(f)
            self._chain = [LedgerEntryAudit.model_validate(item) for item in raw_entries]
        except (json.JSONDecodeError, ValidationError, OSError):
            self._chain = []


# Natural alias
AuditLedgerEngine = LedgerEngineAudit
