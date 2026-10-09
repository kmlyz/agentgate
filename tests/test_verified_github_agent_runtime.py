"""Integration & runtime tests for Verified GitHub Agent ADK and deployment artifacts."""

from pathlib import Path

import pytest
import yaml
from google.adk.agents import Agent
from pydantic import ValidationError

from agentgate.guardrails.adapters.git.schemas import (
    BranchProposal,
    BranchType,
    CommitProposal,
    CommitType,
    PullRequestProposal,
)
from agentgate.guardrails.core.gate import ApprovalGate
from agentgate.guardrails.core.models import ProposalStatus
from blueprints.verified_github_agent import (
    RuntimeAgentGithub,
    create_github_agent_runtime,
    execute_approved_proposal,
    list_pending_proposals,
    propose_branch,
    propose_commit,
    propose_pr,
    root_agent,
)


class TestVerifiedGitHubAgentADKInit:
    """Verifies Google ADK Agent configuration, model, and callbacks."""

    def test_root_agent_configuration(self):
        assert isinstance(root_agent, Agent)
        assert root_agent.name == "verified_github_agent"
        assert root_agent.model == "gemini-3.8-flash"
        assert root_agent.before_tool_callback is not None
        assert len(root_agent.tools) == 5

        tool_names = [getattr(t, "__name__", str(t)) for t in root_agent.tools]
        assert "propose_branch" in tool_names
        assert "propose_commit" in tool_names
        assert "propose_pr" in tool_names
        assert "execute_approved_proposal" in tool_names
        assert "list_pending_proposals" in tool_names

    def test_custom_runtime_instantiation(self):
        gate = ApprovalGate(storage_path=None)
        agent = create_github_agent_runtime(
            approval_gate=gate,
            agent_name="custom_github_agent",
            model="gemini-3.8-flash",
        )
        assert isinstance(agent, Agent)
        assert agent.name == "custom_github_agent"
        assert agent.before_tool_callback is not None


class TestVerifiedGitHubAgentTools:
    """Verifies type safety and schema enforcement on blueprint tools."""

    def test_propose_branch_tool_valid(self):
        res = propose_branch(
            branch_type=BranchType.FEAT,
            branch_name="oauth-login",
            base_branch="main",
            ticket_id="AUTH-10",
        )
        assert res["status"] == "pending_approval"
        assert res["full_branch_name"] == "feat/oauth-login-auth-10"
        assert "git checkout -b feat/oauth-login-auth-10 main" in res["rendered_message"]

    def test_propose_commit_tool_valid(self):
        res = propose_commit(
            branch="feat/oauth-login",
            commit_type=CommitType.FEAT,
            scope="auth",
            short_summary="implement oauth provider login",
            ticket_id="AUTH-10",
        )
        assert res["status"] == "pending_approval"
        assert "feat(auth): implement oauth provider login [AUTH-10]" in res["rendered_message"]

    def test_propose_commit_tool_rejects_banned_phrase(self):
        with pytest.raises(ValidationError, match="banned phrasing"):
            propose_commit(
                branch="main",
                commit_type=CommitType.FIX,
                scope="core",
                short_summary="fix crash (ai generated)",
            )

    def test_propose_pr_tool_valid(self):
        res = propose_pr(
            title_type=CommitType.FEAT,
            title_scope="auth",
            title_summary="implement oauth provider login",
            head_branch="feat/oauth-login",
            base_branch="main",
        )
        assert res["status"] == "pending_approval"
        assert "feat(auth): implement oauth provider login" in res["rendered_message"]

    def test_list_pending_proposals_empty_and_populated(self):
        gate = ApprovalGate()
        gate.clear()
        assert len(list_pending_proposals()) == 0

        # Submit one proposal into gate
        from agentgate.guardrails.adapters.git.schemas import BranchProposal
        prop = BranchProposal(branch_type=BranchType.FEAT, branch_name="test-branch")
        rec = gate.submit_proposal(prop)

        pending = list_pending_proposals()
        assert len(pending) == 1
        assert pending[0]["proposal_id"] == rec.proposal_id
        assert pending[0]["status"] == "pending_approval"
        gate.clear()


class TestVerifiedGitHubAgentRuntimeInterception:
    """Verifies end-to-end tool call interception via RuntimeGuardrailToolCallback."""

    def test_runtime_intercepts_valid_proposal(self):
        gate = ApprovalGate(storage_path=None)
        runtime = RuntimeAgentGithub(approval_gate=gate)
        cb = runtime.guardrail_callback

        payload = {
            "branch": "feat/api-v2",
            "commit_type": "feat",
            "scope": "api",
            "short_summary": "add rate limiter middleware",
            "ticket_id": "API-42",
        }
        res = cb.intercept_runtime_tool_call("propose_commit", payload)

        assert res["status"] == "pending_approval"
        assert "proposal_id" in res
        record = gate.get_record(res["proposal_id"])
        assert record is not None
        assert record.status == ProposalStatus.PENDING_APPROVAL
        assert (
            record.rendered_message
            == "feat(api): add rate limiter middleware [API-42]"
        )

    def test_runtime_rejects_extra_fields_injection(self):
        gate = ApprovalGate(storage_path=None)
        runtime = RuntimeAgentGithub(approval_gate=gate)
        cb = runtime.guardrail_callback

        malicious_payload = {
            "branch": "main",
            "commit_type": "feat",
            "scope": "core",
            "short_summary": "clean code",
            "malicious_injected_argument": "rm -rf /",
        }
        res = cb.intercept_runtime_tool_call("propose_commit", malicious_payload)

        assert res["status"] == "rejected"
        assert res["error"] == "REJECTED BY DETERMINISTIC GUARDRAIL"
        assert len(gate.list_pending()) == 0

    def test_runtime_blocks_unauthorized_execution(self):
        gate = ApprovalGate(storage_path=None)
        runtime = RuntimeAgentGithub(approval_gate=gate)
        cb = runtime.guardrail_callback

        # 1. No proposal_id
        res_no_id = cb.intercept_runtime_tool_call("execute_approved_proposal", {})
        assert res_no_id["status"] == "blocked"

        # 2. Proposal exists but is still PENDING_APPROVAL
        payload = {
            "branch_type": "fix",
            "branch_name": "hotfix-null",
        }
        staged = cb.intercept_runtime_tool_call("propose_branch", payload)
        prop_id = staged["proposal_id"]

        res_unapproved = cb.intercept_runtime_tool_call(
            "execute_approved_proposal", {"proposal_id": prop_id}
        )
        assert res_unapproved["status"] == "blocked"
        assert "pending_approval" in res_unapproved["error"]

    def test_runtime_executes_after_operator_approval(self):
        gate = ApprovalGate(storage_path=None)
        runtime = RuntimeAgentGithub(approval_gate=gate)
        cb = runtime.guardrail_callback

        payload = {
            "branch_type": "feat",
            "branch_name": "payments-stripe",
        }
        staged = cb.intercept_runtime_tool_call("propose_branch", payload)
        prop_id = staged["proposal_id"]

        # Operator approves in gate
        gate.approve(prop_id)

        # Execution proceeds deterministically
        res = cb.intercept_runtime_tool_call(
            "execute_approved_proposal", {"proposal_id": prop_id, "dry_run": True}
        )
        assert res["status"] == "executed"
        assert "[DRY_RUN]" in res["output"]
        assert gate.get_record(prop_id).status == ProposalStatus.EXECUTED


class TestExecuteApprovedProposalDirect:
    """Verifies direct execution of execute_approved_proposal tool with approval gate and git adapter."""

    @pytest.fixture
    def isolated_gate(self) -> ApprovalGate:
        return ApprovalGate(storage_path=None)

    def test_execute_nonexistent_proposal_fails(self, isolated_gate: ApprovalGate):
        res = execute_approved_proposal("prop_doesnotexist", gate=isolated_gate)
        assert res["status"] == "failed"
        assert "not found" in res["error"]

    def test_execute_unapproved_proposal_blocked(self, isolated_gate: ApprovalGate):
        prop = BranchProposal(branch_type=BranchType.FEAT, branch_name="login-flow")
        rec = isolated_gate.submit_proposal(prop)
        assert rec.status == ProposalStatus.PENDING_APPROVAL

        res = execute_approved_proposal(rec.proposal_id, gate=isolated_gate)
        assert res["status"] == "blocked"
        assert "EXECUTION_BLOCKED" in res["error"]
        assert res["current_status"] == "pending_approval"

    def test_execute_approved_commit_proposal(self, isolated_gate: ApprovalGate):
        prop = CommitProposal(
            branch="feat/auth",
            commit_type=CommitType.FEAT,
            scope="auth",
            short_summary="add jwt token verification",
        )
        rec = isolated_gate.submit_proposal(prop)
        isolated_gate.approve(rec.proposal_id)

        res = execute_approved_proposal(rec.proposal_id, dry_run=True, gate=isolated_gate)
        assert res["status"] == "executed"
        assert res["action"] == "commit"
        assert "[DRY_RUN]" in res["output"]
        assert isolated_gate.get_record(rec.proposal_id).status == ProposalStatus.EXECUTED

    def test_execute_approved_pr_proposal(self, isolated_gate: ApprovalGate):
        prop = PullRequestProposal(
            title_type=CommitType.FIX,
            title_scope="cache",
            title_summary="fix memory leak on redis disconnect",
            head_branch="fix/redis-leak",
            base_branch="main",
        )
        rec = isolated_gate.submit_proposal(prop)
        isolated_gate.approve(rec.proposal_id)

        res = execute_approved_proposal(rec.proposal_id, dry_run=True, gate=isolated_gate)
        assert res["status"] == "executed"
        assert res["action"] == "pull_request"
        assert "[DRY_RUN]" in res["output"]
        assert isolated_gate.get_record(rec.proposal_id).status == ProposalStatus.EXECUTED


class TestVerifiedGitHubAgentDeploymentArtifacts:
    """Verifies presence and configuration integrity of Cloud Run and Agents CLI files."""

    @pytest.fixture
    def blueprint_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent / "blueprints" / "verified_github_agent"

    def test_dockerfile_contents(self, blueprint_dir: Path):
        dockerfile = blueprint_dir / "Dockerfile"
        assert dockerfile.exists(), "Dockerfile must exist in blueprint root."
        content = dockerfile.read_text(encoding="utf-8")
        assert "FROM python:3.12-slim" in content
        assert "ENV PORT=8080" in content
        assert "RUN pip install --no-cache-dir uv" in content
        assert "google.adk.server" in content
        assert "blueprints.verified_github_agent.github_agent_runtime" in content

    def test_agents_cli_manifest_yaml(self, blueprint_dir: Path):
        manifest_file = blueprint_dir / "agents-cli-manifest.yaml"
        assert manifest_file.exists(), "agents-cli-manifest.yaml must exist."

        with open(manifest_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert data["manifest_version"] == "1.0"
        assert data["name"] == "verified-github-agent"
        assert data["framework"] == "adk"
        assert data["runtime_target"] == "cloud_run"
        assert data["entrypoint"] == "blueprints.verified_github_agent.github_agent_runtime:root_agent"
        assert data["guardrails"]["enforce_strict_schemas"] is True
        assert data["guardrails"]["approval_gate"] is True
        assert data["cloud_run"]["port"] == 8080

    def test_pyproject_and_env_example(self, blueprint_dir: Path):
        pyproject = blueprint_dir / "pyproject.toml"
        assert pyproject.exists()
        py_content = pyproject.read_text(encoding="utf-8")
        assert 'name = "verified-github-agent"' in py_content
        assert "google-adk" in py_content

        env_example = blueprint_dir / ".env.example"
        assert env_example.exists()
        env_content = env_example.read_text(encoding="utf-8")
        assert "GEMINI_API_KEY=" in env_content
        assert "PORT=8080" in env_content
