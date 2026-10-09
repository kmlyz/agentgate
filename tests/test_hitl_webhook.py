"""Comprehensive tests for Slack/Webhook interactive Human-in-the-Loop approval gate."""

import json
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from agentgate.guardrails.adapters.git import CommitProposal, CommitType
from agentgate.guardrails.adapters.sql import (
    MigrationProposalSql,
    SqlDialect,
    SqlOperationType,
)
from agentgate.guardrails.core.gate import ApprovalGate
from agentgate.guardrails.core.models import ProposalStatus
from agentgate.hitl import (
    GenericWebhookDecision,
    HmacSecurityHitl,
    SlackActionBlock,
    SlackBlockKitDispatcher,
    SlackInteractivePayload,
    SlackUser,
    WebhookDecisionType,
    create_hitl_receiver_app,
)


class TestHitlSchemas:
    """Validate strict Pydantic v2 schemas and extra='forbid' constraint on webhook models."""

    def test_slack_user_valid(self) -> None:
        user = SlackUser(id="U0123456789", username="kemal.security")
        assert user.id == "U0123456789"
        assert user.username == "kemal.security"

    def test_slack_user_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            SlackUser(
                id="U0123456789",
                username="kemal",
                unauthorized_token="secret_token",
            )

    def test_slack_action_block_valid(self) -> None:
        action = SlackActionBlock(
            action_id="approve_proposal",
            value="prop_12345678",
        )
        assert action.action_id == "approve_proposal"
        assert action.value == "prop_12345678"

    def test_slack_action_block_invalid_action(self) -> None:
        with pytest.raises(ValidationError):
            SlackActionBlock(
                action_id="unauthorized_bypass",  # Invalid action_id
                value="prop_12345678",
            )

    def test_slack_interactive_payload_valid(self) -> None:
        payload = SlackInteractivePayload(
            type="block_actions",
            user=SlackUser(id="U0987654321", username="admin_ops"),
            actions=[
                SlackActionBlock(action_id="approve_proposal", value="prop_abcdef12"),
            ],
            response_url="https://hooks.slack.com/actions/T00/B00/X00",
        )
        assert payload.user.username == "admin_ops"
        assert payload.actions[0].value == "prop_abcdef12"

    def test_generic_webhook_decision_valid(self) -> None:
        decision = GenericWebhookDecision(
            proposal_id="prop_deadbeef",
            decision=WebhookDecisionType.APPROVE,
            operator_id="operator@agentgate-pro.internal",
            reason="Approved per change ticket CR-4042",
        )
        assert decision.decision == WebhookDecisionType.APPROVE
        assert decision.proposal_id == "prop_deadbeef"


class TestHitlSecurityHmac:
    """Validate Slack v0 HMAC-SHA256 signature calculation, verification, and TTL replay attacks."""

    SECRET = "test_slack_signing_secret_12345"

    def test_valid_signature_verification(self) -> None:
        body = b'payload={"test": "data"}'
        timestamp = int(time.time())
        sig = HmacSecurityHitl.generate_slack_signature(body, timestamp, self.SECRET)

        is_valid, reason = HmacSecurityHitl.verify_slack_signature(
            body=body,
            timestamp_header=str(timestamp),
            signature_header=sig,
            signing_secret=self.SECRET,
        )
        assert is_valid
        assert reason is None

    def test_invalid_signature_rejected(self) -> None:
        body = b'payload={"test": "data"}'
        timestamp = int(time.time())

        is_valid, reason = HmacSecurityHitl.verify_slack_signature(
            body=body,
            timestamp_header=str(timestamp),
            signature_header="v0=invalid_tampered_hash_00000000000000000000",
            signing_secret=self.SECRET,
        )
        assert not is_valid
        assert reason is not None
        assert "mismatch" in reason.lower()

    def test_replay_attack_rejected_when_timestamp_expired(self) -> None:
        body = b'payload={"test": "data"}'
        current_time = 1700000000.0
        expired_timestamp = int(current_time - 305)  # 305 seconds ago (> 300s window)
        sig = HmacSecurityHitl.generate_slack_signature(body, expired_timestamp, self.SECRET)

        is_valid, reason = HmacSecurityHitl.verify_slack_signature(
            body=body,
            timestamp_header=str(expired_timestamp),
            signature_header=sig,
            signing_secret=self.SECRET,
            current_time=current_time,
            max_age_seconds=300,
        )
        assert not is_valid
        assert reason is not None
        assert "replay attack" in reason.lower()

    def test_missing_headers_rejected(self) -> None:
        body = b"data"
        is_valid, reason = HmacSecurityHitl.verify_slack_signature(
            body=body,
            timestamp_header=None,
            signature_header="v0=xyz",
            signing_secret=self.SECRET,
        )
        assert not is_valid
        assert "missing slack timestamp" in reason.lower()


class TestSlackDispatcher:
    """Validate formatting of Block Kit card messages for Git and SQL proposals."""

    def test_build_sql_proposal_card(self, tmp_path) -> None:
        gate = ApprovalGate(storage_path=tmp_path / "test_proposals.json")
        prop = MigrationProposalSql(
            dialect=SqlDialect.SQLITE,
            operation_type=SqlOperationType.CREATE_TABLE,
            target_table="accounts",
            migration_sql="CREATE TABLE accounts (id INTEGER PRIMARY KEY);",
            rollback_sql="-- rollback note",
            description="Create accounts table",
        )
        record = gate.submit_proposal(prop)

        card = SlackBlockKitDispatcher.build_proposal_card(record)
        assert "blocks" in card
        blocks = card["blocks"]

        # Verify Header and Details
        header = blocks[0]
        assert "SQL MIGRATION" in header["text"]["text"]

        # Verify Code Snippet block
        code_block = [b for b in blocks if "CREATE TABLE accounts" in str(b)]
        assert len(code_block) > 0

        # Verify Action Buttons
        actions_block = blocks[-1]
        assert actions_block["type"] == "actions"
        buttons = actions_block["elements"]
        assert len(buttons) == 2
        assert buttons[0]["action_id"] == "approve_proposal"
        assert buttons[0]["value"] == record.proposal_id
        assert buttons[1]["action_id"] == "reject_proposal"
        assert buttons[1]["value"] == record.proposal_id

    def test_build_git_proposal_card(self, tmp_path) -> None:
        gate = ApprovalGate(storage_path=tmp_path / "test_proposals.json")
        commit_prop = CommitProposal(
            branch="feat/auth",
            commit_type=CommitType.FEAT,
            scope="core",
            short_summary="implement jwt token refresh",
        )
        record = gate.submit_proposal(commit_prop)

        card = SlackBlockKitDispatcher.build_proposal_card(record)
        header = card["blocks"][0]
        assert "GIT COMMIT" in header["text"]["text"]


class TestHitlReceiverServer:
    """Validate FastAPI Webhook Receiver endpoints with signed callbacks and gate state mutation."""

    SECRET = "slack_secret_key_secure_99"

    @pytest.fixture
    def setup_gate_and_client(self, tmp_path) -> tuple[ApprovalGate, TestClient, str]:
        gate = ApprovalGate(storage_path=tmp_path / "receiver_proposals.json")
        app = create_hitl_receiver_app(gate=gate, signing_secret=self.SECRET)
        client = TestClient(app)
        return gate, client, self.SECRET

    def test_health_check(self, setup_gate_and_client) -> None:
        _, client, _ = setup_gate_and_client
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_slack_action_approve_lifecycle(self, setup_gate_and_client) -> None:
        gate, client, secret = setup_gate_and_client
        prop = MigrationProposalSql(
            dialect=SqlDialect.SQLITE,
            operation_type=SqlOperationType.CREATE_INDEX,
            target_table="users",
            migration_sql="CREATE INDEX idx_users_email ON users(email);",
            rollback_sql="DROP INDEX idx_users_email;",
            description="Index users email",
        )
        record = gate.submit_proposal(prop)
        prop_id = record.proposal_id

        # Construct Slack interaction payload
        payload_data = {
            "type": "block_actions",
            "user": {"id": "U12345678", "username": "security_admin"},
            "actions": [{"action_id": "approve_proposal", "value": prop_id}],
        }
        encoded_body = urlencode({"payload": json.dumps(payload_data)}).encode("utf-8")
        timestamp = int(time.time())
        signature = HmacSecurityHitl.generate_slack_signature(encoded_body, timestamp, secret)

        response = client.post(
            "/webhook/slack/actions",
            content=encoded_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": str(timestamp),
                "X-Slack-Signature": signature,
            },
        )
        assert response.status_code == 200
        assert "APPROVED by @security_admin" in response.json()["text"]

        # Verify Gate state transition
        updated_rec = gate.get_record(prop_id)
        assert updated_rec is not None
        assert updated_rec.status == ProposalStatus.APPROVED

    def test_slack_action_reject_lifecycle(self, setup_gate_and_client) -> None:
        gate, client, secret = setup_gate_and_client
        prop = MigrationProposalSql(
            dialect=SqlDialect.SQLITE,
            operation_type=SqlOperationType.CREATE_TABLE,
            target_table="logs",
            migration_sql="CREATE TABLE logs (msg TEXT);",
            rollback_sql="-- rollback note",
            description="Create logs table",
        )
        record = gate.submit_proposal(prop)
        prop_id = record.proposal_id

        payload_data = {
            "type": "block_actions",
            "user": {"id": "U12345678", "username": "lead_sec"},
            "actions": [{"action_id": "reject_proposal", "value": prop_id}],
        }
        encoded_body = urlencode({"payload": json.dumps(payload_data)}).encode("utf-8")
        timestamp = int(time.time())
        signature = HmacSecurityHitl.generate_slack_signature(encoded_body, timestamp, secret)

        response = client.post(
            "/webhook/slack/actions",
            content=encoded_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": str(timestamp),
                "X-Slack-Signature": signature,
            },
        )
        assert response.status_code == 200
        assert "REJECTED by @lead_sec" in response.json()["text"]

        updated_rec = gate.get_record(prop_id)
        assert updated_rec is not None
        assert updated_rec.status == ProposalStatus.REJECTED
        assert "lead_sec" in updated_rec.rejection_reason

    def test_slack_action_invalid_hmac_unauthorized(self, setup_gate_and_client) -> None:
        gate, client, _ = setup_gate_and_client
        prop = MigrationProposalSql(
            dialect=SqlDialect.SQLITE,
            operation_type=SqlOperationType.CREATE_TABLE,
            target_table="tokens",
            migration_sql="CREATE TABLE tokens (id INT);",
            rollback_sql="-- rollback note",
            description="Create tokens",
        )
        record = gate.submit_proposal(prop)

        payload_data = {
            "type": "block_actions",
            "user": {"id": "U12345678", "username": "attacker"},
            "actions": [{"action_id": "approve_proposal", "value": record.proposal_id}],
        }
        encoded_body = urlencode({"payload": json.dumps(payload_data)}).encode("utf-8")

        response = client.post(
            "/webhook/slack/actions",
            content=encoded_body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": str(int(time.time())),
                "X-Slack-Signature": "v0=fraudulent_unauthorized_hash_00000000000",
            },
        )
        assert response.status_code == 401
        assert "Signature verification failed" in response.json()["detail"]
        assert gate.get_record(record.proposal_id).status == ProposalStatus.PENDING_APPROVAL

    def test_generic_decision_webhook(self, setup_gate_and_client) -> None:
        gate, client, _ = setup_gate_and_client
        prop = MigrationProposalSql(
            dialect=SqlDialect.SQLITE,
            operation_type=SqlOperationType.CREATE_TABLE,
            target_table="configs",
            migration_sql="CREATE TABLE configs (k TEXT, v TEXT);",
            rollback_sql="-- rollback note",
            description="Create configs",
        )
        record = gate.submit_proposal(prop)

        resp = client.post(
            "/webhook/generic/decision",
            json={
                "proposal_id": record.proposal_id,
                "decision": "approve",
                "operator_id": "sso_admin_99",
                "reason": "Authorized via CI/CD orchestration gate",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert gate.get_record(record.proposal_id).status == ProposalStatus.APPROVED
