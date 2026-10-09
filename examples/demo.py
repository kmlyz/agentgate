"""AgentGate Quickstart & End-to-End Execution Demo.

Demonstrates:
1. Strict schema proposal validation (Pydantic v2 extra="forbid").
2. Enqueuing into ApprovalGate in PENDING_APPROVAL state.
3. Operator authorization (HITL approval transition).
4. Deterministic adapter dry-run execution.
5. Immutable SHA-256 audit ledger verification.
"""

import tempfile
from pathlib import Path

from agentgate.guardrails.adapters.git import (
    CommitProposal,
    CommitType,
    GitGuardrailAdapter,
)
from agentgate.guardrails.core import ApprovalGate


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_file = Path(tmp_dir) / "proposals.json"
        gate = ApprovalGate(storage_path=storage_file)
        adapter = GitGuardrailAdapter()

        print("=" * 60)
        print("1. Creating typed proposal (Pydantic v2 extra='forbid')")
        print("=" * 60)
        proposal = CommitProposal(
            branch="main",
            commit_type=CommitType.FEAT,
            scope="core",
            short_summary="add deterministic execution gate",
            ticket_id="GATE-101",
        )
        print(f"Rendered commit message: {proposal.render_message()}")

        print("\n" + "=" * 60)
        print("2. Staging proposal into gate")
        print("=" * 60)
        record = gate.stage(proposal)
        print(f"Proposal ID : {record.proposal_id}")
        print(f"State       : {record.status.value}")

        pending = gate.list_pending()
        print(f"Pending count: {len(pending)}")

        print("\n" + "=" * 60)
        print("3. Human-in-the-Loop operator authorization")
        print("=" * 60)
        gate.approve(record.proposal_id, operator_id="security_lead@agentgate.dev")
        approved_record = gate.get_record(record.proposal_id)
        assert approved_record is not None
        print(f"Updated state: {approved_record.status.value}")

        print("\n" + "=" * 60)
        print("4. Deterministic adapter execution (dry-run)")
        print("=" * 60)
        success, output = adapter.execute_commit(approved_record, dry_run=True)
        print(f"Execution OK : {success}")
        print(f"Output       : {output.strip()}")

        # Transition to EXECUTED
        gate.mark_executed(record.proposal_id, operator_id="ci_runner@agentgate.dev")
        final_record = gate.get_record(record.proposal_id)
        assert final_record is not None
        print(f"Final state  : {final_record.status.value}")

        print("\n" + "=" * 60)
        print("5. Cryptographic audit ledger verification")
        print("=" * 60)
        if gate.ledger:
            is_valid, err = gate.ledger.verify_integrity()
            print(f"Ledger blocks count : {len(gate.ledger.chain)}")
            print(f"Chain integrity OK  : {is_valid} (error: {err})")

        print("\nDemo completed successfully.")


if __name__ == "__main__":
    main()
