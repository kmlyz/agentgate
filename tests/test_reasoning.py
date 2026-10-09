"""Comprehensive tests for vendor-agnostic reasoning layer and Gemini integration.

Verifies BaseReasoningEngine contracts, MockReasoningEngine determinism,
GeminiReasoningEngine structured output generation, and end-to-end
VerifiedGitHubAgent natural language workflow execution.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, ConfigDict, Field

from agentgate.guardrails.adapters.git import (
    BranchProposal,
    BranchType,
    CommitProposal,
    CommitType,
    PullRequestProposal,
)
from agentgate.guardrails.core import ApprovalGate, ProposalStatus
from agentgate.reasoning import (
    DEFAULT_GEMINI_MODEL,
    BaseReasoningEngine,
    GeminiReasoningEngine,
    MockReasoningEngine,
    ReasoningError,
)
from blueprints.verified_github_agent import (
    TaskSpecification,
    VerifiedGitHubAgent,
)


class SampleStrictSchema(BaseModel):
    """Test schema enforcing extra='forbid'."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., pattern=r"^[a-z]+$")
    score: int = Field(..., ge=0, le=100)


# ============================================================================
# 1. Base Reasoning Contracts
# ============================================================================


class TestBaseReasoningContracts:
    """Verifies interface contracts and exception handling."""

    def test_abstract_class_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            BaseReasoningEngine()  # type: ignore[abstract]

    def test_reasoning_error_inheritance(self):
        err = ReasoningError("test error")
        assert isinstance(err, Exception)
        assert str(err) == "test error"


# ============================================================================
# 2. Mock Reasoning Engine
# ============================================================================


class TestMockReasoningEngine:
    """Verifies MockReasoningEngine deterministic behaviors and error injection."""

    def test_mock_returns_model_instance(self):
        expected = SampleStrictSchema(name="antigravity", score=99)
        mock_engine = MockReasoningEngine(default_response=expected)

        result = mock_engine.extract_structured(
            prompt="extract score for antigravity",
            schema=SampleStrictSchema,
        )
        assert result == expected
        assert len(mock_engine.call_history) == 1
        assert mock_engine.call_history[0]["prompt"] == "extract score for antigravity"

    def test_mock_validates_dictionary_payload(self):
        mock_engine = MockReasoningEngine(default_response={"name": "agentgate", "score": 85})

        result = mock_engine.extract_structured(
            prompt="get agentgate score",
            schema=SampleStrictSchema,
        )
        assert isinstance(result, SampleStrictSchema)
        assert result.name == "agentgate"
        assert result.score == 85

    def test_mock_validates_json_string_payload(self):
        json_data = '{"name": "gemini", "score": 100}'
        mock_engine = MockReasoningEngine(default_response=json_data)

        result = mock_engine.extract_structured("prompt", SampleStrictSchema)
        assert result.name == "gemini"
        assert result.score == 100

    def test_mock_callable_handler(self):
        def handler(prompt: str, schema: type[BaseModel]):
            return {"name": "dynamic", "score": len(prompt)}

        mock_engine = MockReasoningEngine(default_response=handler)
        result = mock_engine.extract_structured("12345", SampleStrictSchema)
        assert result.name == "dynamic"
        assert result.score == 5

    def test_mock_rejects_schema_violation_with_reasoning_error(self):
        # score out of range (150 > 100)
        mock_engine = MockReasoningEngine(default_response={"name": "invalid", "score": 150})
        with pytest.raises(ReasoningError, match="failed schema validation"):
            mock_engine.extract_structured("prompt", SampleStrictSchema)

    def test_mock_rejects_extra_fields_with_reasoning_error(self):
        # extra field injection
        mock_engine = MockReasoningEngine(
            default_response={"name": "extra", "score": 50, "injected": "exploit"}
        )
        with pytest.raises(ReasoningError, match="failed schema validation"):
            mock_engine.extract_structured("prompt", SampleStrictSchema)

    def test_mock_error_simulation(self):
        mock_engine = MockReasoningEngine(raise_error=RuntimeError("Simulated network outage"))
        with pytest.raises(ReasoningError, match="Simulated mock failure"):
            mock_engine.extract_structured("prompt", SampleStrictSchema)

    def test_mock_no_response_configured(self):
        mock_engine = MockReasoningEngine()
        with pytest.raises(ReasoningError, match="no response configured"):
            mock_engine.extract_structured("prompt", SampleStrictSchema)

    def test_mock_async_extraction(self):
        expected = SampleStrictSchema(name="asyncflow", score=90)
        mock_engine = MockReasoningEngine(default_response=expected)

        result = asyncio.run(
            mock_engine.aextract_structured(
                prompt="async test",
                schema=SampleStrictSchema,
                system_instruction="system prompt",
            )
        )
        assert result == expected
        assert mock_engine.call_history[0]["system_instruction"] == "system prompt"


# ============================================================================
# 3. Gemini Reasoning Engine
# ============================================================================


class TestGeminiReasoningEngine:
    """Verifies GeminiReasoningEngine configuration, SDK integration, and error handling."""

    def test_default_model_and_override(self):
        mock_client = MagicMock()
        engine_default = GeminiReasoningEngine(client=mock_client)
        assert engine_default.model == DEFAULT_GEMINI_MODEL
        assert engine_default.model == "gemini-3.8-flash"

        engine_custom = GeminiReasoningEngine(model="gemini-3.8-pro", client=mock_client)
        assert engine_custom.model == "gemini-3.8-pro"

    def test_api_key_resolution(self, monkeypatch):
        # Priority 1: Explicit parameter
        mock_client_init = MagicMock()
        monkeypatch.setattr("google.genai.Client", mock_client_init)

        GeminiReasoningEngine(api_key="explicit_key_123")
        mock_client_init.assert_called_with(api_key="explicit_key_123")

        # Priority 2: Environment variable
        mock_client_init.reset_mock()
        monkeypatch.setenv("GEMINI_API_KEY", "env_key_456")

        GeminiReasoningEngine()
        mock_client_init.assert_called_with(api_key="env_key_456")

    def test_extract_structured_synchronous_success(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"name": "success", "score": 95}'
        mock_client.models.generate_content.return_value = mock_response

        engine = GeminiReasoningEngine(client=mock_client)
        result = engine.extract_structured(
            prompt="create user",
            schema=SampleStrictSchema,
            system_instruction="be precise",
        )

        assert isinstance(result, SampleStrictSchema)
        assert result.name == "success"
        assert result.score == 95

        # Verify call arguments
        mock_client.models.generate_content.assert_called_once()
        _, kwargs = mock_client.models.generate_content.call_args
        assert kwargs["model"] == "gemini-3.8-flash"
        assert kwargs["contents"] == "create user"

        config = kwargs["config"]
        assert config.response_mime_type == "application/json"
        assert config.response_schema == SampleStrictSchema
        assert config.system_instruction == "be precise"

    def test_aextract_structured_asynchronous_success(self):
        mock_client = MagicMock()
        mock_client.aio = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"name": "asynctest", "score": 88}'
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        engine = GeminiReasoningEngine(client=mock_client)
        result = asyncio.run(
            engine.aextract_structured(
                prompt="async test prompt",
                schema=SampleStrictSchema,
            )
        )

        assert isinstance(result, SampleStrictSchema)
        assert result.name == "asynctest"
        assert result.score == 88
        mock_client.aio.models.generate_content.assert_called_once()

    def test_extract_structured_empty_response_raises_error(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = ""  # Empty text
        mock_client.models.generate_content.return_value = mock_response

        engine = GeminiReasoningEngine(client=mock_client)
        with pytest.raises(ReasoningError, match="empty response or null text"):
            engine.extract_structured("test", SampleStrictSchema)

    def test_extract_structured_schema_violation_raises_error(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"name": "INVALID_UPPERCASE", "score": 50}'
        mock_client.models.generate_content.return_value = mock_response

        engine = GeminiReasoningEngine(client=mock_client)
        with pytest.raises(ReasoningError, match="Validation error against schema"):
            engine.extract_structured("test", SampleStrictSchema)

    def test_extract_structured_sdk_exception_wrapped_in_reasoning_error(self):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("Quota exceeded")

        engine = GeminiReasoningEngine(client=mock_client)
        with pytest.raises(ReasoningError, match="Gemini API content generation failed"):
            engine.extract_structured("test", SampleStrictSchema)


# ============================================================================
# 4. End-to-End Natural Language Workflow with VerifiedGitHubAgent
# ============================================================================


class TestEndToEndNaturalLanguageWorkflow:
    """Verifies natural language task extraction and HITL approval pipeline."""

    def test_planning_without_reasoning_engine_raises_error(self):
        agent = VerifiedGitHubAgent(reasoning_engine=None)
        with pytest.raises(ReasoningError, match="No reasoning_engine configured"):
            agent.plan_from_natural_language("add auth feature")

    def test_natural_language_workflow_planning_and_dry_run_execution(self):
        gate = ApprovalGate()
        valid_spec_data = {
            "branch_type": "feat",
            "branch_name": "oauth2-refresh",
            "scope": "auth",
            "summary": "implement oauth2 token refresh",
            "ticket_id": "AUTH-101",
            "base_branch": "main",
        }
        mock_engine = MockReasoningEngine(default_response=valid_spec_data)
        agent = VerifiedGitHubAgent(approval_gate=gate, reasoning_engine=mock_engine)

        spec, proposals = agent.plan_from_natural_language(
            prompt="AUTH-101: implement oauth2 token refresh logic in auth module",
        )

        assert isinstance(spec, TaskSpecification)
        assert spec.branch_type == BranchType.FEAT
        assert spec.branch_name == "oauth2-refresh"
        assert spec.scope == "auth"
        assert spec.summary == "implement oauth2 token refresh"
        assert spec.ticket_id == "AUTH-101"

        # Assert 3 proposals created and staged in PENDING_APPROVAL
        assert len(proposals) == 3
        branch_rec, commit_rec, pr_rec = proposals

        for prop in proposals:
            assert prop.status == ProposalStatus.PENDING_APPROVAL

        assert isinstance(branch_rec.proposal, BranchProposal)
        assert branch_rec.proposal.full_branch_name == "feat/oauth2-refresh-auth-101"

        assert isinstance(commit_rec.proposal, CommitProposal)
        assert commit_rec.proposal.commit_type == CommitType.FEAT
        assert "feat(auth): implement oauth2 token refresh [AUTH-101]" in commit_rec.rendered_message

        assert isinstance(pr_rec.proposal, PullRequestProposal)
        assert "feat(auth): implement oauth2 token refresh [AUTH-101]" in pr_rec.rendered_message

        # Approve and execute Stage 1 & Stage 2 deterministically
        gate.approve(branch_rec.proposal_id)
        success_b, out_b = agent.execute_proposal(branch_rec.proposal_id, dry_run=True)
        assert success_b
        assert "[DRY_RUN] Branch created" in out_b
        assert gate.get_record(branch_rec.proposal_id).status == ProposalStatus.EXECUTED

        gate.approve(commit_rec.proposal_id)
        success_c, out_c = agent.execute_proposal(commit_rec.proposal_id, dry_run=True)
        assert success_c
        assert "[DRY_RUN] Committed message" in out_c
        assert gate.get_record(commit_rec.proposal_id).status == ProposalStatus.EXECUTED

    def test_natural_language_workflow_parameter_overrides(self):
        spec_without_ticket = {
            "branch_type": "fix",
            "branch_name": "null-pointer",
            "scope": "core",
            "summary": "fix null pointer exception",
            "base_branch": "main",
        }
        mock_engine = MockReasoningEngine(default_response=spec_without_ticket)
        agent = VerifiedGitHubAgent(reasoning_engine=mock_engine)

        spec, proposals = agent.plan_from_natural_language(
            prompt="fix null pointer in core",
            base_branch="develop",
            ticket_id="BUG-999",
        )

        assert spec.ticket_id == "BUG-999"
        assert spec.base_branch == "develop"
        assert proposals[0].proposal.ticket_id == "BUG-999"
        assert proposals[0].proposal.base_branch == "develop"

    def test_async_natural_language_workflow(self):
        spec_data = {
            "branch_type": "refactor",
            "branch_name": "clean-interfaces",
            "scope": "reasoning",
            "summary": "refactor engine interfaces",
            "base_branch": "main",
        }
        mock_engine = MockReasoningEngine(default_response=spec_data)
        agent = VerifiedGitHubAgent(reasoning_engine=mock_engine)

        spec, proposals = asyncio.run(
            agent.aplan_from_natural_language(
                prompt="refactor engine interfaces",
            )
        )
        assert spec.branch_type == BranchType.REFACTOR
        assert len(proposals) == 3
