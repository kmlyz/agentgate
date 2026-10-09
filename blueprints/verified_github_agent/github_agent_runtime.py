"""Google ADK 2.0 Runtime & Entrypoint for Verified GitHub Agent.

Integrates the Verified GitHub Agent with Google ADK Agent framework, binds the
RuntimeGuardrailToolCallback before_tool_callback hook, and provides the entrypoint
for Cloud Run container serving and Google Agents CLI lifecycle commands.
"""

from google.adk.agents import Agent

from agentgate.guardrails.adapters.git.adapter import GitGuardrailAdapter
from agentgate.guardrails.core.gate import ApprovalGate
from agentgate.runtime.runtime_callback_guardrail import (
    RuntimeGuardrailToolCallback,
)
from blueprints.verified_github_agent.github_agent_tools import (
    execute_approved_proposal,
    list_pending_proposals,
    propose_branch,
    propose_commit,
    propose_pr,
)


class RuntimeAgentGithub:
    """Runtime factory and wrapper for Verified GitHub Agent."""

    DEFAULT_MODEL = "gemini-3.8-flash"
    DEFAULT_AGENT_NAME = "verified_github_agent"
    DEFAULT_INSTRUCTION = (
        "You are an AgentGate Pro GitHub development assistant operating under strict "
        "deterministic guardrails. You plan branch creation, conventional commits, and "
        "pull requests. NEVER generate free-form mutating git commands directly; all mutating "
        "actions MUST be staged via propose_* tools for Human-in-the-Loop ApprovalGate review. "
        "Only execute proposals when explicitly instructed with a verified, approved proposal_id."
    )

    def __init__(
        self,
        approval_gate: ApprovalGate | None = None,
        git_adapter: GitGuardrailAdapter | None = None,
        model: str = DEFAULT_MODEL,
        agent_name: str = DEFAULT_AGENT_NAME,
    ) -> None:
        self.approval_gate = approval_gate or ApprovalGate()
        self.git_adapter = git_adapter or GitGuardrailAdapter()
        self.model = model
        self.agent_name = agent_name
        self.guardrail_callback = RuntimeGuardrailToolCallback(
            approval_gate=self.approval_gate,
            git_adapter=self.git_adapter,
        )

    def create_agent(self) -> Agent:
        """Create and configure Google ADK Agent instance."""
        return Agent(
            name=self.agent_name,
            model=self.model,
            description=(
                "AgentGate Pro Git/GitHub development assistant protected by "
                "deterministic guardrails and ApprovalGate human authorization."
            ),
            instruction=self.DEFAULT_INSTRUCTION,
            tools=[
                propose_branch,
                propose_commit,
                propose_pr,
                execute_approved_proposal,
                list_pending_proposals,
            ],
            before_tool_callback=self.guardrail_callback.before_tool_callback,
        )


def create_github_agent_runtime(
    approval_gate: ApprovalGate | None = None,
    git_adapter: GitGuardrailAdapter | None = None,
    model: str = RuntimeAgentGithub.DEFAULT_MODEL,
    agent_name: str = RuntimeAgentGithub.DEFAULT_AGENT_NAME,
) -> Agent:
    """Module-level factory to instantiate a configured ADK root agent."""
    runtime = RuntimeAgentGithub(
        approval_gate=approval_gate,
        git_adapter=git_adapter,
        model=model,
        agent_name=agent_name,
    )
    return runtime.create_agent()


# Default root_agent instance conforming to Google Agents CLI entrypoint specification
_default_runtime = RuntimeAgentGithub()
root_agent: Agent = _default_runtime.create_agent()

__all__ = [
    "RuntimeAgentGithub",
    "create_github_agent_runtime",
    "root_agent",
]
