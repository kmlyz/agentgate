"""Comprehensive test suite for cryptographically immutable audit ledger and OpenTelemetry telemetry."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from agentgate.audit import (
    GENESIS_HASH,
    AuditEntryType,
    AuditTracerOtel,
    LedgerEngineAudit,
    LedgerEntryAudit,
    compute_payload_digest,
)
from agentgate.cli.cli_operator_entrypoint import cli
from agentgate.guardrails.adapters.git import CommitProposal, CommitType
from agentgate.guardrails.adapters.sql import (
    MigrationProposalSql,
    SqlDialect,
    SqlOperationType,
)
from agentgate.guardrails.core import ApprovalGate

# ============================================================================
# 1. Schema & Cryptographic Hashing Unit Tests
# ============================================================================


def test_audit_schema_extra_forbid():
    """Verify strict extra='forbid' policy on LedgerEntryAudit."""
    assert LedgerEntryAudit.model_config.get("extra") == "forbid"
    with pytest.raises(ValidationError) as exc:
        LedgerEntryAudit(
            sequence_number=0,
            timestamp_utc="2026-10-09T00:00:00Z",
            proposal_id="prop_12345678",
            domain="core",
            entry_type=AuditEntryType.PROPOSAL_CREATED,
            payload_digest="a" * 64,
            prev_hash="0" * 64,
            current_hash="b" * 64,
            unauthorized_injection="malicious_field",
        )
    errors = exc.value.errors()
    assert any(e["type"] == "extra_forbidden" for e in errors)


def test_compute_payload_digest_deterministic():
    """Verify deterministic SHA-256 generation across dicts, strings, and orders."""
    dict_a = {"key1": "value1", "key2": 123}
    dict_b = {"key2": 123, "key1": "value1"}
    assert compute_payload_digest(dict_a) == compute_payload_digest(dict_b)

    str_digest = compute_payload_digest("hello world")
    assert len(str_digest) == 64
    assert str_digest == compute_payload_digest("hello world")


def test_ledger_entry_hash_verification():
    """Verify internal block calculation and integrity verification."""
    prev = GENESIS_HASH
    digest = compute_payload_digest({"test": "data"})
    calculated_hash = LedgerEntryAudit.calculate_block_hash(
        sequence_number=0,
        timestamp_utc="2026-10-09T00:00:00Z",
        prev_hash=prev,
        payload_digest=digest,
        entry_type=AuditEntryType.PROPOSAL_CREATED,
        proposal_id="prop_abcdef12",
        domain="git",
        operator_id="operator@agentgate.dev",
    )
    entry = LedgerEntryAudit(
        sequence_number=0,
        timestamp_utc="2026-10-09T00:00:00Z",
        prev_hash=prev,
        payload_digest=digest,
        entry_type=AuditEntryType.PROPOSAL_CREATED,
        proposal_id="prop_abcdef12",
        domain="git",
        operator_id="operator@agentgate.dev",
        current_hash=calculated_hash,
    )
    assert entry.verify_block_integrity() is True


# ============================================================================
# 2. Sequential Block Appending & Integrity Verification
# ============================================================================


def test_empty_ledger_integrity():
    """An empty audit ledger is considered valid."""
    engine = LedgerEngineAudit(storage_path=None)
    is_valid, err = engine.verify_integrity()
    assert is_valid is True
    assert err is None
    assert len(engine.chain) == 0


def test_sequential_hash_chain_propagation(tmp_path: Path):
    """Verify monotonic sequence and proper prev_hash chaining from Genesis."""
    storage_file = tmp_path / "test_ledger.json"
    engine = LedgerEngineAudit(storage_path=storage_file)

    b0 = engine.append_event(
        proposal_id="prop_11111111",
        domain="git",
        entry_type=AuditEntryType.PROPOSAL_CREATED,
        payload={"commit": "init"},
    )
    assert b0.sequence_number == 0
    assert b0.prev_hash == GENESIS_HASH

    b1 = engine.append_event(
        proposal_id="prop_11111111",
        domain="git",
        entry_type=AuditEntryType.OPERATOR_APPROVED,
        payload={"approved": True},
        operator_id="admin@agentgate.dev",
    )
    assert b1.sequence_number == 1
    assert b1.prev_hash == b0.current_hash

    b2 = engine.append_event(
        proposal_id="prop_22222222",
        domain="sql",
        entry_type=AuditEntryType.PROPOSAL_CREATED,
        payload={"table": "users"},
    )
    assert b2.sequence_number == 2
    assert b2.prev_hash == b1.current_hash

    is_valid, err = engine.verify_integrity()
    assert is_valid is True
    assert err is None


def test_atomic_persistence_and_reloading(tmp_path: Path):
    """Verify ledger state survives disk reloading intact."""
    storage_file = tmp_path / "persistent_ledger.json"
    engine1 = LedgerEngineAudit(storage_path=storage_file)
    engine1.append_event("prop_aaaaaaaa", "git", AuditEntryType.PROPOSAL_CREATED, {"a": 1})
    engine1.append_event("prop_aaaaaaaa", "git", AuditEntryType.OPERATOR_APPROVED, {"a": 2})

    assert storage_file.exists()

    engine2 = LedgerEngineAudit(storage_path=storage_file)
    assert len(engine2.chain) == 2
    assert engine2.chain[0].proposal_id == "prop_aaaaaaaa"
    assert engine2.chain[1].prev_hash == engine2.chain[0].current_hash
    is_valid, err = engine2.verify_integrity()
    assert is_valid is True
    assert err is None


def test_export_audit_trail_filtering():
    """Verify export_audit_trail correctly isolates records by proposal_id."""
    engine = LedgerEngineAudit(storage_path=None)
    engine.append_event("prop_11111111", "git", AuditEntryType.PROPOSAL_CREATED, {"task": 1})
    engine.append_event("prop_22222222", "sql", AuditEntryType.PROPOSAL_CREATED, {"task": 2})
    engine.append_event("prop_11111111", "git", AuditEntryType.OPERATOR_APPROVED, {"task": 1})

    trail_1 = engine.export_audit_trail("prop_11111111")
    trail_2 = engine.export_audit_trail("prop_22222222")
    trail_empty = engine.export_audit_trail("prop_99999999")

    assert len(trail_1) == 2
    assert len(trail_2) == 1
    assert len(trail_empty) == 0


# ============================================================================
# 3. Tamper Detection (Tahrifat Tespiti) Scenarios
# ============================================================================


def test_tamper_detection_modified_payload(tmp_path: Path):
    """Simulate malicious alteration of historical block payload on disk."""
    storage_file = tmp_path / "tamper_ledger.json"
    engine = LedgerEngineAudit(storage_path=storage_file)

    engine.append_event("prop_11111111", "git", AuditEntryType.PROPOSAL_CREATED, {"code": "clean"})
    engine.append_event("prop_11111111", "git", AuditEntryType.OPERATOR_APPROVED, {"approved": True})
    engine.append_event("prop_11111111", "git", AuditEntryType.MUTATION_EXECUTED, {"status": "ok"})

    # Tamper: Alter the payload digest of block 1 directly in persisted JSON
    with open(storage_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    data[1]["payload_digest"] = "f" * 64  # Corrupt digest

    with open(storage_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    tampered_engine = LedgerEngineAudit(storage_path=storage_file)
    is_valid, err = tampered_engine.verify_integrity()
    assert is_valid is False
    assert "Tamper detected" in str(err)
    assert "block 1" in str(err)


def test_tamper_detection_broken_chain(tmp_path: Path):
    """Simulate broken prev_hash link between consecutive blocks."""
    storage_file = tmp_path / "broken_chain.json"
    engine = LedgerEngineAudit(storage_path=storage_file)

    engine.append_event("prop_11111111", "git", AuditEntryType.PROPOSAL_CREATED, {"step": 0})
    engine.append_event("prop_11111111", "git", AuditEntryType.OPERATOR_APPROVED, {"step": 1})

    with open(storage_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Point block 1's prev_hash to a forged hash
    data[1]["prev_hash"] = "e" * 64

    with open(storage_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    tampered_engine = LedgerEngineAudit(storage_path=storage_file)
    is_valid, err = tampered_engine.verify_integrity()
    assert is_valid is False
    assert "Hash chain broken at block 1" in str(err)


def test_tamper_detection_corrupted_genesis(tmp_path: Path):
    """Simulate tampering with the Genesis block prev_hash."""
    storage_file = tmp_path / "genesis_tamper.json"
    engine = LedgerEngineAudit(storage_path=storage_file)

    engine.append_event("prop_11111111", "git", AuditEntryType.PROPOSAL_CREATED, {"init": True})

    with open(storage_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    data[0]["prev_hash"] = "1" * 64  # Must be 0 * 64

    with open(storage_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    tampered_engine = LedgerEngineAudit(storage_path=storage_file)
    is_valid, err = tampered_engine.verify_integrity()
    assert is_valid is False
    assert "Genesis block prev_hash corrupted" in str(err)


def test_tamper_detection_sequence_mismatch(tmp_path: Path):
    """Simulate swapped or deleted block leading to sequence discontinuity."""
    storage_file = tmp_path / "seq_tamper.json"
    engine = LedgerEngineAudit(storage_path=storage_file)

    engine.append_event("prop_11111111", "git", AuditEntryType.PROPOSAL_CREATED, {"seq": 0})
    engine.append_event("prop_11111111", "git", AuditEntryType.OPERATOR_APPROVED, {"seq": 1})

    with open(storage_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    data[1]["sequence_number"] = 99  # Should be 1

    with open(storage_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    tampered_engine = LedgerEngineAudit(storage_path=storage_file)
    is_valid, err = tampered_engine.verify_integrity()
    assert is_valid is False
    assert "Sequence number mismatch at index 1" in str(err)


# ============================================================================
# 4. ApprovalGate Full Lifecycle Integration
# ============================================================================


def test_approval_gate_lifecycle_audit_git(tmp_path: Path):
    """Verify Git proposal full lifecycle is completely logged in the ledger."""
    gate_storage = tmp_path / "proposals.json"
    ledger = LedgerEngineAudit(storage_path=tmp_path / "audit_ledger.json")
    gate = ApprovalGate(storage_path=gate_storage, ledger=ledger)

    proposal = CommitProposal(
        branch="main",
        commit_type=CommitType.FEAT,
        scope="audit",
        short_summary="implement immutable ledger",
        ticket_id="AUDIT-101",
    )

    # 1. Proposal Created
    rec = gate.submit_proposal(proposal)
    assert len(ledger.chain) == 1
    assert ledger.chain[0].entry_type == AuditEntryType.PROPOSAL_CREATED
    assert ledger.chain[0].domain == "git"
    assert ledger.chain[0].proposal_id == rec.proposal_id

    # 2. Operator Approved
    gate.approve(rec.proposal_id, operator_id="security_lead@agentgate.dev")
    assert len(ledger.chain) == 2
    assert ledger.chain[1].entry_type == AuditEntryType.OPERATOR_APPROVED
    assert ledger.chain[1].operator_id == "security_lead@agentgate.dev"
    assert ledger.chain[1].domain == "git"

    # 3. Mutation Executed
    gate.mark_executed(rec.proposal_id, operator_id="ci_runner@agentgate.dev")
    assert len(ledger.chain) == 3
    assert ledger.chain[2].entry_type == AuditEntryType.MUTATION_EXECUTED
    assert ledger.chain[2].domain == "git"

    # Verify overall integrity
    is_valid, err = ledger.verify_integrity()
    assert is_valid is True
    assert err is None


def test_approval_gate_lifecycle_audit_sql(tmp_path: Path):
    """Verify SQL proposal lifecycle with rejection correctly captured in ledger."""
    ledger = LedgerEngineAudit(storage_path=tmp_path / "sql_ledger.json")
    gate = ApprovalGate(storage_path=tmp_path / "sql_props.json", ledger=ledger)

    sql_prop = MigrationProposalSql(
        dialect=SqlDialect.SQLITE,
        operation_type=SqlOperationType.CREATE_TABLE,
        target_table="audit_logs",
        migration_sql="CREATE TABLE audit_logs (id INTEGER PRIMARY KEY);",
        rollback_sql="DROP TABLE IF EXISTS audit_logs;",
        description="add audit table",
    )

    rec = gate.submit_proposal(sql_prop)
    assert len(ledger.chain) == 1
    assert ledger.chain[0].domain == "sql"

    # Reject proposal
    gate.reject(rec.proposal_id, reason="Missing indexes", operator_id="dba@agentgate.dev")
    assert len(ledger.chain) == 2
    assert ledger.chain[1].entry_type == AuditEntryType.OPERATOR_REJECTED
    assert ledger.chain[1].operator_id == "dba@agentgate.dev"
    assert ledger.chain[1].domain == "sql"

    is_valid, err = ledger.verify_integrity()
    assert is_valid is True
    assert err is None


# ============================================================================
# 5. OpenTelemetry Telemetry Collector Tests
# ============================================================================


def test_otel_tracer_span_and_latency():
    """Verify OtelTracerAudit measures execution duration and tracks span status."""
    tracer = AuditTracerOtel()

    with tracer.trace_span("guardrail_inspection", {"domain": "git"}) as span:
        assert span["status"] == "IN_PROGRESS"
        assert span["attributes"]["domain"] == "git"

    summary = tracer.get_metrics_summary()
    assert summary["total_spans_recorded"] == 1
    assert summary["avg_latency_ms"] >= 0.0


def test_otel_tracer_span_error_handling():
    """Verify OtelTracerAudit marks status ERROR and re-raises on exception."""
    tracer = AuditTracerOtel()

    with pytest.raises(RuntimeError), tracer.trace_span("failing_operation") as span:
        raise RuntimeError("simulated error")

    assert span["status"] == "ERROR"
    assert "simulated error" in span["error"]


def test_otel_tracer_mtta_metrics():
    """Verify recording and aggregation of Mean Time to Approve (MTTA)."""
    tracer = AuditTracerOtel()
    tracer.record_approval_latency(12.5)
    tracer.record_approval_latency(7.5)

    summary = tracer.get_metrics_summary()
    assert summary["total_approvals_measured"] == 2
    assert summary["avg_mtta_seconds"] == 10.0

    tracer.clear()
    assert tracer.get_metrics_summary()["total_approvals_measured"] == 0


# ============================================================================
# 6. Operator CLI Audit Subcommands Tests
# ============================================================================


def test_cli_audit_verify_empty(tmp_path: Path):
    """CLI audit verify reports empty state gracefully."""
    empty_file = tmp_path / "empty_ledger.json"
    runner = CliRunner()
    result = runner.invoke(cli, ["audit", "verify", "--storage-path", str(empty_file)])
    assert result.exit_code == 0
    assert "Audit Ledger is empty" in result.output


def test_cli_audit_verify_success(tmp_path: Path):
    """CLI audit verify confirms valid hash chain integrity."""
    ledger_file = tmp_path / "cli_valid_ledger.json"
    engine = LedgerEngineAudit(storage_path=ledger_file)
    engine.append_event("prop_11111111", "git", AuditEntryType.PROPOSAL_CREATED, {"task": "deploy"})
    engine.append_event("prop_11111111", "git", AuditEntryType.OPERATOR_APPROVED, {"ok": True})

    runner = CliRunner()
    result = runner.invoke(cli, ["audit", "verify", "--storage-path", str(ledger_file)])
    assert result.exit_code == 0
    assert "[SECURE] Audit Ledger integrity verified: 2 chained blocks intact." in result.output


def test_cli_audit_verify_tamper_detected(tmp_path: Path):
    """CLI audit verify aborts with non-zero exit code on corrupted chain."""
    ledger_file = tmp_path / "cli_tamper_ledger.json"
    engine = LedgerEngineAudit(storage_path=ledger_file)
    engine.append_event("prop_11111111", "git", AuditEntryType.PROPOSAL_CREATED, {"task": "deploy"})

    with open(ledger_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    data[0]["payload_digest"] = "0" * 64
    with open(ledger_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    runner = CliRunner()
    result = runner.invoke(cli, ["audit", "verify", "--storage-path", str(ledger_file)])
    assert result.exit_code != 0
    assert "[TAMPER DETECTED]" in result.output


def test_cli_audit_trail_command(tmp_path: Path):
    """CLI audit trail outputs full chronological blocks for specified proposal."""
    ledger_file = tmp_path / "cli_trail_ledger.json"
    engine = LedgerEngineAudit(storage_path=ledger_file)
    engine.append_event("prop_12345678", "git", AuditEntryType.PROPOSAL_CREATED, {"cmd": "init"})
    engine.append_event(
        "prop_12345678",
        "git",
        AuditEntryType.OPERATOR_APPROVED,
        {"auth": True},
        operator_id="admin@agentgate.dev",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["audit", "trail", "prop_12345678", "--storage-path", str(ledger_file)])
    assert result.exit_code == 0
    assert "AUDIT TRAIL FOR PROPOSAL [prop_12345678] (2 blocks)" in result.output
    assert "Type: PROPOSAL_CREATED" in result.output
    assert "Type: OPERATOR_APPROVED" in result.output
    assert "Operator:       admin@agentgate.dev" in result.output


def test_cli_audit_trail_not_found(tmp_path: Path):
    """CLI audit trail warns when proposal has no associated blocks."""
    ledger_file = tmp_path / "cli_trail_empty.json"
    runner = CliRunner()
    result = runner.invoke(cli, ["audit", "trail", "prop_unknown9", "--storage-path", str(ledger_file)])
    assert result.exit_code == 0
    assert "No audit records found for proposal 'prop_unknown9'" in result.output
