"""FastAPI Webhook receiver endpoint verifying HMAC signatures and mutating ApprovalGate state."""

import json
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from agentgate.guardrails.core.gate import ApprovalGate
from agentgate.guardrails.core.models import ProposalStatus
from agentgate.hitl.hitl_schemas_webhook import (
    SlackInteractivePayloadHitl,
    WebhookDecisionGenericHitl,
    WebhookDecisionType,
)
from agentgate.hitl.hitl_security_hmac import HmacSecurityHitl


class ServerReceiverHitl:
    """Manages the FastAPI application lifecycle for webhook and Slack HITL decisions."""

    def __init__(
        self,
        gate: ApprovalGate | None = None,
        signing_secret: str | None = None,
    ) -> None:
        self.gate = gate or ApprovalGate()
        self.signing_secret = signing_secret
        self.app = self._build_app()

    def _build_app(self) -> FastAPI:
        """Create and configure the FastAPI web application with secure webhook endpoints."""
        app = FastAPI(
            title="AgentGate HITL Webhook Receiver",
            version="0.3.0",
            description="Secure Slack and generic webhook endpoints for Human-in-the-Loop decision enforcement.",
        )

        @app.get("/health", status_code=status.HTTP_200_OK)
        async def health_check() -> dict[str, str]:
            """Return service operational health status."""
            return {"status": "healthy", "service": "agentgate-hitl-receiver"}

        @app.post("/webhook/slack/actions")
        async def handle_slack_actions(request: Request) -> Response:
            """Process Slack interactive button callbacks with HMAC signature and replay attack verification."""
            raw_body = await request.body()
            timestamp = request.headers.get("X-Slack-Request-Timestamp")
            signature = request.headers.get("X-Slack-Signature")

            # 1. Enforce signature and TTL verification if signing_secret is configured
            if self.signing_secret:
                is_valid, reason = HmacSecurityHitl.verify_slack_signature(
                    body=raw_body,
                    timestamp_header=timestamp,
                    signature_header=signature,
                    signing_secret=self.signing_secret,
                )
                if not is_valid:
                    if reason and "Replay attack" in reason:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Webhook rejected: {reason}",
                        )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Signature verification failed: {reason}",
                    )

            # 2. Extract payload (support urlencoded 'payload={...}' and raw application/json)
            content_type = request.headers.get("content-type", "")
            raw_text = raw_body.decode("utf-8")

            try:
                if "application/x-www-form-urlencoded" in content_type:
                    parsed_qs = parse_qs(raw_text)
                    if "payload" not in parsed_qs or not parsed_qs["payload"]:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Missing 'payload' form field in urlencoded request.",
                        )
                    payload_json = json.loads(parsed_qs["payload"][0])
                else:
                    payload_json = json.loads(raw_text)
            except (json.JSONDecodeError, ValueError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Malformed JSON payload: {exc}",
                ) from exc

            # 3. Validate against strict schema
            try:
                payload = SlackInteractivePayloadHitl.model_validate(payload_json)
            except ValidationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid Slack payload schema: {exc.errors()}",
                ) from exc

            # 4. Process operator decision on first action
            action = payload.actions[0]
            prop_id = action.value
            operator_name = payload.user.username

            record = self.gate.get_record(prop_id)
            if not record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Proposal ID '{prop_id}' was not found in gate registry.",
                )

            if record.status != ProposalStatus.PENDING_APPROVAL:
                return JSONResponse(
                    content={
                        "response_type": "ephemeral",
                        "text": f"⚠️ Proposal '{prop_id}' is already in status '{record.status.value.upper()}'. No state change.",
                    },
                    status_code=status.HTTP_200_OK,
                )

            if action.action_id == "approve_proposal":
                self.gate.approve(prop_id)
                return JSONResponse(
                    content={
                        "response_type": "ephemeral",
                        "text": f"✅ Proposal `{prop_id}` has been APPROVED by @{operator_name}.\nAction: {record.rendered_message}",
                    },
                    status_code=status.HTTP_200_OK,
                )

            if action.action_id == "reject_proposal":
                self.gate.reject(prop_id, reason=f"Rejected via Slack button by @{operator_name}")
                return JSONResponse(
                    content={
                        "response_type": "ephemeral",
                        "text": f"❌ Proposal `{prop_id}` has been REJECTED by @{operator_name}.",
                    },
                    status_code=status.HTTP_200_OK,
                )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown action_id: '{action.action_id}'.",
            )

        @app.post("/webhook/generic/decision")
        async def handle_generic_decision(payload: WebhookDecisionGenericHitl) -> dict[str, Any]:
            """Process generic JSON webhook approval/rejection decisions."""
            record = self.gate.get_record(payload.proposal_id)
            if not record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Proposal ID '{payload.proposal_id}' was not found in gate registry.",
                )

            if record.status != ProposalStatus.PENDING_APPROVAL:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Proposal '{payload.proposal_id}' is already in status '{record.status.value.upper()}'.",
                )

            if payload.decision == WebhookDecisionType.APPROVE:
                self.gate.approve(payload.proposal_id)
            else:
                self.gate.reject(payload.proposal_id, reason=payload.reason)

            return {
                "status": "success",
                "proposal_id": payload.proposal_id,
                "decision": payload.decision.value,
                "operator_id": payload.operator_id,
                "current_status": self.gate.get_record(payload.proposal_id).status.value,  # type: ignore[union-attr]
            }

        return app


# Natural aliases and factory function
HitlWebhookReceiver = ServerReceiverHitl


def create_hitl_receiver_app(
    gate: ApprovalGate | None = None,
    signing_secret: str | None = None,
) -> FastAPI:
    """Convenience factory returning configured FastAPI instance."""
    receiver = ServerReceiverHitl(gate=gate, signing_secret=signing_secret)
    return receiver.app
