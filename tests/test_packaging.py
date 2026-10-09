"""Package metadata, dual CLI entrypoints, and MCP multi-transport test suite."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from agentgate.cli.cli_operator_entrypoint import cli
from agentgate.mcp.server import (
    main as mcp_main,
)
from agentgate.mcp.server import (
    run_server,
)


def test_package_metadata_and_entrypoints():
    """Verify PEP 517/621 build configuration and registered CLI binaries."""
    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    assert pyproject_path.exists()

    import tomllib

    with open(pyproject_path, "rb") as f:
        config = tomllib.load(f)

    # Build system verification
    assert "build-system" in config
    assert config["build-system"]["build-backend"] == "hatchling.build"
    assert "hatchling" in config["build-system"]["requires"]

    # Package structure verification
    wheel_packages = config.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {}).get("wheel", {}).get("packages", [])
    assert "src/agentgate" in wheel_packages
    assert "blueprints" in wheel_packages

    # Script binaries verification
    scripts = config.get("project", {}).get("scripts", {})
    assert "agentgate" in scripts
    assert scripts["agentgate"] == "agentgate.cli:main"
    assert "gate" in scripts
    assert scripts["gate"] == "agentgate.cli:main"
    assert "agentgate-mcp" in scripts
    assert scripts["agentgate-mcp"] == "agentgate.mcp.server:main"


def test_cli_runner_mcp_serve_dispatch():
    """Verify 'agentgate mcp serve --help' exposes transport, host, and port options."""
    runner = CliRunner()
    result = runner.invoke(cli, ["mcp", "serve", "--help"])
    assert result.exit_code == 0
    assert "--transport" in result.output
    assert "--host" in result.output
    assert "--port" in result.output


def test_mcp_server_argument_parser():
    """Verify MCP server CLI argument parsing for stdio, sse, host, and port."""
    with patch("agentgate.mcp.server.run_server") as mock_run:
        mcp_main(["--transport", "sse", "--port", "9090", "--host", "127.0.0.1"])
        mock_run.assert_called_once_with(transport="sse", host="127.0.0.1", port=9090)


def test_mcp_server_env_var_fallback():
    """Verify MCP server falls back to environment variables when flags are omitted."""
    env_overrides = {
        "MCP_TRANSPORT": "streamable-http",
        "PORT": "7070",
        "HOST": "10.0.0.1",
    }
    with (
        patch.dict(os.environ, env_overrides),
        patch("agentgate.mcp.server.run_server") as mock_run,
    ):
        mcp_main([])
        mock_run.assert_called_once_with(transport="streamable-http", host="10.0.0.1", port=7070)


def test_mcp_run_server_invalid_transport_raises():
    """Verify run_server rejects unsupported transport types."""
    with pytest.raises(ValueError, match="Unsupported transport 'invalid'"):
        run_server(transport="invalid")
