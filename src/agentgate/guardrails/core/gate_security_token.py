"""Cryptographic token authority generating and validating single-use HMAC-SHA256 signed approval tokens."""

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any

from pydantic import ValidationError

from agentgate.guardrails.core.models import SignedApprovalToken

DEFAULT_APPROVAL_TTL_SECONDS: float = 1800.0  # 30 minutes
DEFAULT_GATE_SECRET: str = "agentgate_secret_insecure_default_key_change_in_prod"


def _get_signing_secret(override: str | None = None) -> str:
    """Retrieve secret from parameter or environment variable."""
    if override:
        return override
    return os.getenv("AGENTGATE_SIGNING_SECRET", DEFAULT_GATE_SECRET)


class TokenSecurityGate:
    """Authority for issuing and verifying cryptographic single-use approval tokens."""

    @classmethod
    def compute_payload_digest(cls, payload: Any) -> str:
        """Compute canonical SHA-256 hex digest of a payload dictionary or model."""
        if hasattr(payload, "model_dump"):
            raw_data = payload.model_dump()
        elif isinstance(payload, dict):
            raw_data = payload
        else:
            raw_data = {"raw": str(payload)}

        canonical_bytes = json.dumps(raw_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical_bytes).hexdigest()

    @classmethod
    def issue_approval_token(
        cls,
        proposal_id: str,
        payload_sha256: str,
        state_fingerprint: str,
        ttl_seconds: float = DEFAULT_APPROVAL_TTL_SECONDS,
        secret: str | None = None,
    ) -> SignedApprovalToken:
        """Issue an HMAC-SHA256 signed single-use approval token."""
        signing_key = _get_signing_secret(secret)
        nonce = uuid.uuid4().hex
        issued_at = time.time()
        expires_at = issued_at + ttl_seconds

        msg = f"{proposal_id}:{payload_sha256}:{state_fingerprint}:{nonce}:{issued_at}:{expires_at}".encode()
        signature = hmac.new(
            key=signing_key.encode("utf-8"),
            msg=msg,
            digestmod=hashlib.sha256,
        ).hexdigest()

        return SignedApprovalToken(
            proposal_id=proposal_id,
            payload_sha256=payload_sha256,
            state_fingerprint=state_fingerprint,
            nonce=nonce,
            issued_at=issued_at,
            expires_at=expires_at,
            signature=signature,
        )

    @classmethod
    def serialize_token(cls, token: SignedApprovalToken) -> str:
        """Serialize a SignedApprovalToken into an URL-safe base64 string."""
        raw_json = json.dumps(token.model_dump(), sort_keys=True)
        return base64.urlsafe_b64encode(raw_json.encode("utf-8")).decode("utf-8")

    @classmethod
    def deserialize_token(cls, raw_token_str: str) -> SignedApprovalToken:
        """Deserialize an URL-safe base64 string back into a SignedApprovalToken."""
        try:
            decoded_bytes = base64.urlsafe_b64decode(raw_token_str.encode())
            data = json.loads(decoded_bytes.decode())
            return SignedApprovalToken.model_validate(data)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise ValueError(f"Invalid approval token format: {exc}") from exc

    @classmethod
    def verify_approval_token(
        cls,
        token: SignedApprovalToken | str,
        expected_proposal_id: str,
        expected_payload_sha256: str,
        expected_state_fingerprint: str,
        secret: str | None = None,
        current_time: float | None = None,
    ) -> tuple[bool, str | None]:
        """Verify signature, expiry (TTL), payload hash, and state fingerprint.

        Returns (is_valid, failure_reason).
        """
        if isinstance(token, str):
            try:
                tok = cls.deserialize_token(token)
            except ValueError as err:
                return False, str(err)
        else:
            tok = token

        signing_key = _get_signing_secret(secret)

        # 1. Proposal ID check
        if tok.proposal_id != expected_proposal_id:
            return False, f"Proposal ID mismatch: token is for '{tok.proposal_id}', expected '{expected_proposal_id}'."

        # 2. Signature verification
        msg = f"{tok.proposal_id}:{tok.payload_sha256}:{tok.state_fingerprint}:{tok.nonce}:{tok.issued_at}:{tok.expires_at}".encode()
        expected_sig = hmac.new(
            key=signing_key.encode("utf-8"),
            msg=msg,
            digestmod=hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(tok.signature, expected_sig):
            return False, "E_INVALID_SIGNATURE: Approval token signature verification failed."

        # 3. TTL Expiration check
        now = current_time if current_time is not None else time.time()
        if now > tok.expires_at:
            return False, f"E_TOKEN_EXPIRED: Approval token expired at {tok.expires_at} (current: {now})."

        # 4. Payload tampering check (Confused Deputy defense)
        if tok.payload_sha256 != expected_payload_sha256:
            return False, (
                f"E_PAYLOAD_TAMPERED: Payload hash mismatch. Token '{tok.payload_sha256}' "
                f"!= Execution target '{expected_payload_sha256}'."
            )

        # 5. State drift check (TOCTOU defense)
        if tok.state_fingerprint != expected_state_fingerprint:
            return False, (
                f"E_STATE_DRIFT: Environment state fingerprint mismatch. Token staged at '{tok.state_fingerprint}' "
                f"!= Current environment '{expected_state_fingerprint}'."
            )

        return True, None


def issue_gate_security_token(
    proposal_id: str,
    payload_sha256: str,
    state_fingerprint: str,
    ttl_seconds: float = DEFAULT_APPROVAL_TTL_SECONDS,
    secret: str | None = None,
) -> SignedApprovalToken:
    """Convenience helper to issue token conforming to hierarchical naming."""
    return TokenSecurityGate.issue_approval_token(
        proposal_id=proposal_id,
        payload_sha256=payload_sha256,
        state_fingerprint=state_fingerprint,
        ttl_seconds=ttl_seconds,
        secret=secret,
    )


def verify_gate_security_token(
    token: SignedApprovalToken | str,
    expected_proposal_id: str,
    expected_payload_sha256: str,
    expected_state_fingerprint: str,
    secret: str | None = None,
    current_time: float | None = None,
) -> tuple[bool, str | None]:
    """Convenience helper to verify token conforming to hierarchical naming."""
    return TokenSecurityGate.verify_approval_token(
        token=token,
        expected_proposal_id=expected_proposal_id,
        expected_payload_sha256=expected_payload_sha256,
        expected_state_fingerprint=expected_state_fingerprint,
        secret=secret,
        current_time=current_time,
    )
