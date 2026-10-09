"""Verified GitHub Agent Blueprint package."""

import sys
from pathlib import Path

# Auto-resolve workspace root and src directory into sys.path
_ws_root = Path(__file__).resolve().parent.parent.parent
_src_dir = _ws_root / "src"
if str(_ws_root) not in sys.path:
    sys.path.insert(0, str(_ws_root))
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from blueprints.verified_github_agent.agent import (
    TaskSpecification,
    VerifiedGitHubAgent,
)
from blueprints.verified_github_agent.github_agent_runtime import (
    RuntimeAgentGithub,
    create_github_agent_runtime,
    root_agent,
)
from blueprints.verified_github_agent.github_agent_tools import (
    ToolsAgentGithub,
    execute_approved_proposal,
    list_pending_proposals,
    propose_branch,
    propose_commit,
    propose_pr,
)

__all__ = [
    "RuntimeAgentGithub",
    "TaskSpecification",
    "ToolsAgentGithub",
    "VerifiedGitHubAgent",
    "create_github_agent_runtime",
    "execute_approved_proposal",
    "list_pending_proposals",
    "propose_branch",
    "propose_commit",
    "propose_pr",
    "root_agent",
]

