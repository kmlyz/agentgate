"""Adversarial Evaluation Runner for AgentGate Guardrails.

Simulates adversarial attacks and red-teaming scenarios against the runtime guardrail
interceptor, evaluating outcomes against deterministic security rubrics.
"""

import json
import sys
from pathlib import Path
from typing import Any

# Ensure src directory is on sys.path for direct CLI/script execution
_src_dir = Path(__file__).resolve().parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from agentgate.guardrails.core.gate import ApprovalGate
from agentgate.runtime.runtime_callback_guardrail import (
    RuntimeGuardrailToolCallback,
)

DEFAULT_EVALSET_PATH = (
    Path(__file__).resolve().parent / "eval_adversarial_injection.evalset.json"
)
DEFAULT_RUBRICS_PATH = Path(__file__).resolve().parent / "eval_rubrics_security.json"


class AdversarialEvalRunner:
    """Automated evaluation engine simulating red-team attacks against guardrails."""

    def __init__(
        self,
        evalset_path: Path | str | None = None,
        rubrics_path: Path | str | None = None,
        callback: RuntimeGuardrailToolCallback | None = None,
    ) -> None:
        self.evalset_path = Path(evalset_path) if evalset_path else DEFAULT_EVALSET_PATH
        self.rubrics_path = Path(rubrics_path) if rubrics_path else DEFAULT_RUBRICS_PATH
        # Isolated in-memory approval gate to avoid disk pollution during evaluation
        gate = ApprovalGate(storage_path=None)
        self.callback = callback or RuntimeGuardrailToolCallback(approval_gate=gate)

    def load_evalset(self) -> dict[str, Any]:
        """Load and return the adversarial evaluation dataset."""
        if not self.evalset_path.exists():
            raise FileNotFoundError(f"Evalset file not found at: {self.evalset_path}")
        with open(self.evalset_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_rubrics(self) -> dict[str, Any]:
        """Load and return security rubrics configuration."""
        if not self.rubrics_path.exists():
            raise FileNotFoundError(f"Rubrics file not found at: {self.rubrics_path}")
        with open(self.rubrics_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def evaluate_single_case(self, case: dict[str, Any]) -> dict[str, Any]:
        """Simulate a single adversarial case and evaluate guardrail defense."""
        case_id = case.get("eval_case_id", "unknown_case")
        category = case.get("attack_category", "general")
        simulated_call = case.get("simulated_tool_call", {})
        tool_name = simulated_call.get("tool", "")
        args = simulated_call.get("args", {})
        expected = case.get("expected_guardrail_outcome", {})

        # Execute call against runtime guardrail interceptor
        result = self.callback.intercept_runtime_tool_call(tool_name, args)

        passed = True
        failure_reasons: list[str] = []

        if result is None:
            passed = False
            failure_reasons.append(
                f"VULNERABILITY: Tool '{tool_name}' was allowed to execute without interception."
            )
        else:
            actual_status = result.get("status")
            expected_status = expected.get("status")

            if actual_status != expected_status:
                passed = False
                failure_reasons.append(
                    f"Status mismatch: expected '{expected_status}', got '{actual_status}'"
                )

            # Check expected error substring if specified
            expected_error_contains = expected.get("error_contains")
            if expected_error_contains:
                err_text = str(result.get("error", ""))
                details_text = " ".join(str(d) for d in result.get("details", []))
                combined_err = f"{err_text} {details_text}".lower()
                if expected_error_contains.lower() not in combined_err:
                    passed = False
                    failure_reasons.append(
                        f"Expected error to contain '{expected_error_contains}', "
                        f"got '{combined_err}'"
                    )

            # Check expected rendered message substring if specified
            expected_msg_contains = expected.get("rendered_message_contains")
            if expected_msg_contains:
                actual_msg = str(result.get("rendered_message", ""))
                if expected_msg_contains not in actual_msg:
                    passed = False
                    failure_reasons.append(
                        f"Expected rendered message to contain '{expected_msg_contains}', "
                        f"got '{actual_msg}'"
                    )

        return {
            "eval_case_id": case_id,
            "attack_category": category,
            "passed": passed,
            "vulnerability_detected": not passed,
            "actual_outcome": result,
            "failure_reasons": failure_reasons,
        }

    def execute_eval_adversarial_suite(
        self, evalset_path: str | None = None
    ) -> dict[str, Any]:
        """Execute the entire adversarial suite and compute rubric scores."""
        if evalset_path:
            self.evalset_path = Path(evalset_path)

        dataset = self.load_evalset()
        cases = dataset.get("eval_cases", [])

        case_results: list[dict[str, Any]] = []
        passed_count = 0

        # Rubric counters
        category_stats: dict[str, dict[str, int]] = {}

        for case in cases:
            res = self.evaluate_single_case(case)
            case_results.append(res)
            cat = res["attack_category"]

            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "passed": 0}
            category_stats[cat]["total"] += 1

            if res["passed"]:
                passed_count += 1
                category_stats[cat]["passed"] += 1

        total_count = len(cases)
        overall_score = (passed_count / total_count) if total_count > 0 else 0.0

        rubric_breakdown = {}
        for cat, stats in category_stats.items():
            rate = stats["passed"] / stats["total"] if stats["total"] > 0 else 0.0
            rubric_breakdown[cat] = {
                "total_cases": stats["total"],
                "passed_cases": stats["passed"],
                "success_rate": rate,
            }

        return {
            "dataset_name": dataset.get("name", "adversarial_evalset"),
            "total_cases": total_count,
            "passed_cases": passed_count,
            "failed_cases": total_count - passed_count,
            "overall_score": overall_score,
            "security_posture": "SECURE" if overall_score == 1.0 else "VULNERABLE",
            "rubric_breakdown": rubric_breakdown,
            "case_results": case_results,
        }


def execute_eval_runner_adversarial(
    evalset_path: str | None = None,
) -> dict[str, Any]:
    """Standalone module function to execute adversarial evaluation suite."""
    runner = AdversarialEvalRunner(evalset_path=evalset_path)
    return runner.execute_eval_adversarial_suite()


if __name__ == "__main__":
    report = execute_eval_runner_adversarial()
    print(json.dumps(report, indent=2))
