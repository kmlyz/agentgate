"""Deterministic HMAC-SHA256 signature verification and replay attack protection for Slack webhooks."""

import hashlib
import hmac
import time


class HmacSecurityHitl:
    """Security engine for validating Slack webhook signatures and enforcing TTL replay gates."""

    DEFAULT_MAX_AGE_SECONDS: int = 300  # 5-minute replay window

    @classmethod
    def generate_slack_signature(
        cls,
        body: bytes,
        timestamp: int | str,
        signing_secret: str,
    ) -> str:
        """Compute Slack v0 HMAC-SHA256 signature string."""
        base_string = f"v0:{timestamp}:{body.decode('utf-8')}"
        computed_hash = hmac.new(
            key=signing_secret.encode("utf-8"),
            msg=base_string.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return f"v0={computed_hash}"

    @classmethod
    def verify_slack_signature(
        cls,
        body: bytes,
        timestamp_header: str | None,
        signature_header: str | None,
        signing_secret: str,
        current_time: float | None = None,
        max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    ) -> tuple[bool, str | None]:
        """Verify Slack signature against signing secret and check replay timestamp.

        Returns:
            Tuple of (is_valid, rejection_reason).
        """
        if not signing_secret:
            return False, "Server signing secret is not configured."

        if not timestamp_header:
            return False, "Missing Slack timestamp header ('X-Slack-Request-Timestamp')."

        if not signature_header:
            return False, "Missing Slack signature header ('X-Slack-Signature')."

        try:
            req_timestamp = int(timestamp_header)
        except ValueError:
            return False, "Invalid timestamp header: must be an integer Unix epoch."

        # Replay Attack Prevention (TTL check)
        now = current_time if current_time is not None else time.time()
        age = abs(now - req_timestamp)
        if age > max_age_seconds:
            return False, f"Replay attack detected: request timestamp is outside valid window ({int(age)}s > {max_age_seconds}s)."

        # Constant-time comparison
        expected_sig = cls.generate_slack_signature(body, req_timestamp, signing_secret)
        if not hmac.compare_digest(expected_sig, signature_header):
            return False, "Invalid Slack signature: signature hash mismatch."

        return True, None


# Natural alias
SlackHmacSecurity = HmacSecurityHitl
