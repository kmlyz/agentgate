"""Tests for Adversarial Evaluation Suite and Security Runner."""

from evals.eval_runner_adversarial import (
    AdversarialEvalRunner,
    execute_eval_runner_adversarial,
)


class TestAdversarialEvalArtifacts:
    """Tests file schema validity and presence of eval artifacts."""

    def test_evalset_file_schema_integrity(self):
        runner = AdversarialEvalRunner()
        dataset = runner.load_evalset()
        assert "eval_cases" in dataset
        assert len(dataset["eval_cases"]) >= 6, (
            "Evalset must contain at least 6-8 adversarial cases."
        )

        required_keys = {
            "eval_case_id",
            "attack_category",
            "simulated_tool_call",
            "expected_guardrail_outcome",
        }
        for case in dataset["eval_cases"]:
            missing = required_keys - set(case.keys())
            assert not missing, (
                f"Case '{case.get('eval_case_id')}' missing keys: {missing}"
            )

    def test_rubrics_file_schema_integrity(self):
        runner = AdversarialEvalRunner()
        rubrics_data = runner.load_rubrics()
        assert "rubrics" in rubrics_data
        rubrics = rubrics_data["rubrics"]
        expected_rubrics = {
            "deterministic_guardrail_compliance",
            "zero_unauthorized_execution",
            "state_integrity",
            "banned_phrase_filtering",
        }
        missing = expected_rubrics - set(rubrics.keys())
        assert not missing, f"Missing required security rubrics: {missing}"


class TestAdversarialDefenseExecution:
    """Tests that the deterministic guardrail neutralizes 100% of adversarial attacks."""

    def test_all_adversarial_attacks_neutralized(self):
        runner = AdversarialEvalRunner()
        report = runner.execute_eval_adversarial_suite()

        assert report["overall_score"] == 1.0, (
            f"Security vulnerability detected! Score: {report['overall_score']}, "
            f"Failed cases: {report['failed_cases']}"
        )
        assert report["security_posture"] == "SECURE"
        assert report["failed_cases"] == 0
        assert report["passed_cases"] == report["total_cases"]

    def test_individual_attack_categories_breakdown(self):
        runner = AdversarialEvalRunner()
        report = runner.execute_eval_adversarial_suite()

        breakdown = report["rubric_breakdown"]
        # Ensure every individual attack category achieved 100% defense success
        for category, stats in breakdown.items():
            assert stats["success_rate"] == 1.0, (
                f"Attack category '{category}' failed to achieve 100% defense: {stats}"
            )

    def test_baseline_legitimate_proposal_passes(self):
        runner = AdversarialEvalRunner()
        dataset = runner.load_evalset()
        baseline_case = next(
            c
            for c in dataset["eval_cases"]
            if c["eval_case_id"] == "scenario_valid_baseline_legitimate"
        )
        eval_result = runner.evaluate_single_case(baseline_case)

        assert eval_result["passed"] is True
        assert eval_result["actual_outcome"]["status"] == "pending_approval"
        assert (
            "feat(auth): add token revocation handler [AUTH-50]"
            in eval_result["actual_outcome"]["rendered_message"]
        )

    def test_module_level_runner_function(self):
        report = execute_eval_runner_adversarial()
        assert report["overall_score"] == 1.0
        assert report["security_posture"] == "SECURE"
