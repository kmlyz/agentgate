"""Integration tests for Scaffolding Pipeline Engine and Quality Gate."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agentgate.scaffold import (
    EnginePipelineScaffold,
    QualityGateError,
    execute_scaffold_pipeline_create,
    verify_scaffold_quality_gate,
)
from evals.eval_runner_adversarial import AdversarialEvalRunner


class TestScaffoldTemplateRendering:
    """Tests template synthesis for Cloud Run and Google Agents CLI standards."""

    def test_dockerfile_template_generation_valid(self):
        engine = EnginePipelineScaffold()
        dockerfile = engine.render_dockerfile("test-agent", port=8080)

        assert "FROM python:3.12-slim" in dockerfile
        assert "ENV PORT=8080" in dockerfile
        assert "EXPOSE 8080" in dockerfile
        assert "google.adk.server" in dockerfile

    def test_manifest_template_generation_valid(self):
        engine = EnginePipelineScaffold()
        manifest = engine.render_manifest(
            "secure-agent", port=8080, region="europe-west1"
        )

        assert 'name: "secure-agent"' in manifest
        assert 'framework: "adk"' in manifest
        assert 'runtime_target: "cloud_run"' in manifest
        assert 'entrypoint: "app.agent:root_agent"' in manifest
        assert (
            'runtime_callback: "agentgate.runtime.RuntimeGuardrailToolCallback"'
            in manifest
        )
        assert 'region: "europe-west1"' in manifest

    def test_agent_entrypoint_embeds_guardrail_callback(self):
        engine = EnginePipelineScaffold()
        agent_code = engine.render_agent_entrypoint("payroll-agent")

        assert "from google.adk.agents import Agent" in agent_code
        assert (
            "from agentgate.runtime import RuntimeGuardrailToolCallback"
            in agent_code
        )
        assert "guardrail_callback = RuntimeGuardrailToolCallback()" in agent_code
        assert (
            "before_tool_callback=guardrail_callback.before_tool_callback" in agent_code
        )
        assert "root_agent = Agent(" in agent_code
        assert 'name="payroll-agent"' in agent_code


class TestScaffoldQualityGate:
    """Tests security quality gate enforcement before project creation."""

    def test_quality_gate_passes_with_perfect_score(self):
        engine = EnginePipelineScaffold()
        qg_report = engine.run_quality_gate()

        assert qg_report["status"] == "passed"
        assert qg_report["overall_score"] == 1.0
        assert qg_report["security_posture"] == "SECURE"

    def test_quality_gate_blocks_deployment_on_vulnerability(self):
        mock_runner = MagicMock(spec=AdversarialEvalRunner)
        mock_runner.execute_eval_adversarial_suite.return_value = {
            "overall_score": 0.75,
            "security_posture": "VULNERABLE",
            "failed_cases": 2,
        }

        engine = EnginePipelineScaffold(eval_runner=mock_runner)

        with pytest.raises(QualityGateError) as exc_info:
            engine.run_quality_gate()

        assert "QUALITY_GATE_BLOCKED" in str(exc_info.value)
        assert "75.0%" in str(exc_info.value)

    def test_scaffold_creation_aborted_when_quality_gate_fails(self, tmp_path: Path):
        mock_runner = MagicMock(spec=AdversarialEvalRunner)
        mock_runner.execute_eval_adversarial_suite.return_value = {
            "overall_score": 0.50,
            "security_posture": "VULNERABLE",
            "failed_cases": 4,
        }

        engine = EnginePipelineScaffold(eval_runner=mock_runner)
        out_dir = tmp_path / "failing_agent"

        with pytest.raises(QualityGateError):
            engine.create_agent("failing-agent", out_dir, enforce_quality_gate=True)

        # Verify no files were created due to security blockage
        assert not out_dir.exists()


class TestScaffoldAgentLifecycle:
    """Tests end-to-end agent directory generation and naming validation."""

    def test_agent_name_validation_constraints(self):
        engine = EnginePipelineScaffold()

        # Valid names
        engine.validate_agent_name("valid-agent")
        engine.validate_agent_name("agent123")
        engine.validate_agent_name("a")

        # Invalid names
        with pytest.raises(ValueError):
            engine.validate_agent_name("INVALID_UPPERCASE")
        with pytest.raises(ValueError):
            engine.validate_agent_name("agent with spaces")
        with pytest.raises(ValueError):
            engine.validate_agent_name("-leading-hyphen")
        with pytest.raises(ValueError):
            engine.validate_agent_name(
                "name-that-is-way-too-long-exceeding-twenty-six-chars"
            )

    def test_scaffold_create_agent_end_to_end(self, tmp_path: Path):
        engine = EnginePipelineScaffold()
        target_dir = tmp_path / "my_ops_agent"

        report = engine.create_agent(
            "my-ops-agent", target_dir, enforce_quality_gate=True
        )

        assert report["status"] == "scaffolded"
        assert report["agent_name"] == "my-ops-agent"
        assert report["quality_gate"]["status"] == "passed"

        # Verify all required files exist
        assert (target_dir / "app" / "__init__.py").exists()
        assert (target_dir / "app" / "agent.py").exists()
        assert (target_dir / "Dockerfile").exists()
        assert (target_dir / "agents-cli-manifest.yaml").exists()
        assert (target_dir / "pyproject.toml").exists()
        assert (target_dir / ".env.example").exists()

        # Check content integrity
        manifest_text = (target_dir / "agents-cli-manifest.yaml").read_text(
            encoding="utf-8"
        )
        assert 'name: "my-ops-agent"' in manifest_text
        assert 'runtime_target: "cloud_run"' in manifest_text

    def test_module_level_helpers(self, tmp_path: Path):
        qg = verify_scaffold_quality_gate()
        assert qg["status"] == "passed"

        target_dir = tmp_path / "helper_agent"
        report = execute_scaffold_pipeline_create(
            "helper-agent", target_dir, enforce_quality_gate=False
        )
        assert report["status"] == "scaffolded"
        assert (target_dir / "Dockerfile").exists()
