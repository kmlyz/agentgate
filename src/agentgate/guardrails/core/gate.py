"""Universal Human-in-the-Loop Approval Gate state machine with atomic persistence."""

import json
import uuid
from pathlib import Path
from typing import Any

from agentgate.guardrails.core.models import (
    BaseProposal,
    ProposalRecord,
    ProposalStatus,
)

DEFAULT_STORAGE_PATH = Path(".tmp/guardrail_proposals.json")


class ApprovalGate:
    """Universal state machine and gatekeeper for proposals.

    Operates completely decoupled from specific domains (Git, Docker, etc.).
    Supports optional or default atomic disk persistence for CLI/session resilience.
    """

    def __init__(
        self,
        storage_path: Path | str | None = DEFAULT_STORAGE_PATH,
        ledger: Any | None = None,
        enable_audit: bool = True,
    ) -> None:
        self._storage_path = Path(storage_path) if storage_path else None
        self._registry: dict[str, ProposalRecord] = {}
        if ledger is not None:
            self._ledger = ledger
        elif enable_audit:
            try:
                from agentgate.audit.audit_engine_ledger import (
                    DEFAULT_LEDGER_STORAGE_PATH,
                    LedgerEngineAudit,
                )
                if self._storage_path == DEFAULT_STORAGE_PATH:
                    ledger_path = DEFAULT_LEDGER_STORAGE_PATH
                elif self._storage_path is not None:
                    ledger_path = self._storage_path.parent / f"{self._storage_path.stem}_audit_ledger.json"
                else:
                    ledger_path = None
                self._ledger = LedgerEngineAudit(storage_path=ledger_path)
            except (ImportError, OSError, ValueError):
                self._ledger = None
        else:
            self._ledger = None

        if self._storage_path:
            self._load_from_disk()

    @property
    def ledger(self) -> Any | None:
        """Attached audit ledger engine if configured."""
        return self._ledger

    @ledger.setter
    def ledger(self, value: Any) -> None:
        self._ledger = value

    def _resolve_domain(self, proposal: Any) -> str:
        if hasattr(proposal, "migration_sql") or hasattr(proposal, "rollback_sql"):
            return "sql"
        if hasattr(proposal, "branch") or hasattr(proposal, "branch_name") or hasattr(proposal, "head_branch"):
            return "git"
        if hasattr(proposal, "domain"):
            d = str(proposal.domain)
            if d in ("git", "sql", "core", "system"):
                return d
        if isinstance(proposal, dict):
            if "migration_sql" in proposal or "rollback_sql" in proposal:
                return "sql"
            if "branch" in proposal or "branch_name" in proposal or "head_branch" in proposal:
                return "git"
            if proposal.get("domain") in ("git", "sql", "core", "system"):
                return str(proposal["domain"])
        return "core"

    def _record_audit(
        self,
        proposal_id: str,
        entry_type: str,
        payload: Any,
        operator_id: str | None = None,
        domain: str = "core",
    ) -> None:
        if self._ledger and hasattr(self._ledger, "append_event"):
            self._ledger.append_event(
                proposal_id=proposal_id,
                domain=domain,
                entry_type=entry_type,
                payload=payload,
                operator_id=operator_id,
            )

    def submit_proposal(self, proposal: BaseProposal | Any) -> ProposalRecord:
        """Enqueue a proposal into PENDING_APPROVAL state."""
        proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
        rendered = proposal.render_message() if hasattr(proposal, "render_message") else str(proposal)
        record = ProposalRecord(
            proposal_id=proposal_id,
            proposal=proposal,
            rendered_message=rendered,
            status=ProposalStatus.PENDING_APPROVAL,
        )
        self._registry[proposal_id] = record
        self._save_to_disk()

        domain = self._resolve_domain(proposal)
        payload_dump = proposal.model_dump() if hasattr(proposal, "model_dump") else str(proposal)
        self._record_audit(
            proposal_id=proposal_id,
            entry_type="proposal_created",
            payload=payload_dump,
            domain=domain,
        )
        return record

    stage = submit_proposal

    def approve(self, proposal_id: str, operator_id: str | None = None) -> ProposalRecord:
        """Transitions proposal to APPROVED state."""
        record = self._get_record(proposal_id)
        if record.status != ProposalStatus.PENDING_APPROVAL:
            raise ValueError(f"Proposal '{proposal_id}' cannot be approved from status '{record.status}'.")
        record.status = ProposalStatus.APPROVED
        self._save_to_disk()
        domain = self._resolve_domain(record.proposal)
        self._record_audit(
            proposal_id=proposal_id,
            entry_type="operator_approved",
            payload={"rendered_message": record.rendered_message},
            operator_id=operator_id,
            domain=domain,
        )
        return record

    def reject(
        self,
        proposal_id: str,
        reason: str = "Rejected by operator",
        operator_id: str | None = None,
    ) -> ProposalRecord:
        """Transitions proposal to REJECTED state."""
        record = self._get_record(proposal_id)
        if record.status != ProposalStatus.PENDING_APPROVAL:
            raise ValueError(f"Proposal '{proposal_id}' cannot be rejected from status '{record.status}'.")
        record.status = ProposalStatus.REJECTED
        record.rejection_reason = reason
        self._save_to_disk()
        domain = self._resolve_domain(record.proposal)
        self._record_audit(
            proposal_id=proposal_id,
            entry_type="operator_rejected",
            payload={"reason": reason},
            operator_id=operator_id,
            domain=domain,
        )
        return record

    def mark_executed(self, proposal_id: str, operator_id: str | None = None) -> ProposalRecord:
        """Transitions proposal to EXECUTED state.

        Strictly enforces that the proposal was previously APPROVED.
        """
        record = self._get_record(proposal_id)
        if record.status != ProposalStatus.APPROVED:
            raise ValueError(f"Proposal '{proposal_id}' cannot be executed without prior APPROVAL.")
        record.status = ProposalStatus.EXECUTED
        self._save_to_disk()
        domain = self._resolve_domain(record.proposal)
        self._record_audit(
            proposal_id=proposal_id,
            entry_type="mutation_executed",
            payload={"rendered_message": record.rendered_message},
            operator_id=operator_id,
            domain=domain,
        )
        return record

    def get_record(self, proposal_id: str) -> ProposalRecord | None:
        """Retrieve proposal record by unique identifier, or None if not found."""
        return self._registry.get(proposal_id)

    def list_pending(self) -> list[ProposalRecord]:
        """List all proposals currently in PENDING_APPROVAL status."""
        return [
            rec
            for rec in self._registry.values()
            if rec.status == ProposalStatus.PENDING_APPROVAL
        ]

    def clear(self) -> None:
        """Clear all in-memory proposals and wipe persisted state."""
        self._registry.clear()
        if self._ledger and hasattr(self._ledger, "clear"):
            self._ledger.clear()
        if self._storage_path and self._storage_path.exists():
            try:
                self._storage_path.unlink()
            except OSError:
                pass

    def _get_record(self, proposal_id: str) -> ProposalRecord:
        record = self._registry.get(proposal_id)
        if not record:
            raise KeyError(f"Proposal ID '{proposal_id}' not found.")
        return record

    def _load_from_disk(self) -> None:
        if not self._storage_path or not self._storage_path.exists():
            return
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                raw_dict = json.load(f)
            for pid, data in raw_dict.items():
                self._registry[pid] = ProposalRecord(
                    proposal_id=data["proposal_id"],
                    proposal=data["proposal"],
                    rendered_message=data["rendered_message"],
                    status=ProposalStatus(data["status"]),
                    rejection_reason=data.get("rejection_reason"),
                )
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            # Corrupted or unreadable state falls back safely to empty memory
            pass

    def _save_to_disk(self) -> None:
        if not self._storage_path:
            return
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            records_data = {}
            for pid, rec in self._registry.items():
                prop_data = rec.proposal.model_dump() if hasattr(rec.proposal, "model_dump") else rec.proposal
                records_data[pid] = {
                    "proposal_id": rec.proposal_id,
                    "proposal": prop_data,
                    "rendered_message": rec.rendered_message,
                    "status": rec.status.value if hasattr(rec.status, "value") else str(rec.status),
                    "rejection_reason": rec.rejection_reason,
                }
            temp_path = self._storage_path.with_suffix(".tmp_atomic")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(records_data, f, indent=2, ensure_ascii=False)
            temp_path.replace(self._storage_path)
        except OSError:
            pass
