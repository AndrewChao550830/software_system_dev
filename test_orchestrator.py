import unittest
from unittest.mock import patch
from orchestrator import run_gate_validation, Artifact, GateResult


def _make_artifact(skill_id="skill_se_requirement", quality_score=85, artifact=None, risk_list=None):
    return Artifact(
        skill_id=skill_id,
        stage_id="requirement",
        artifact=artifact if artifact is not None else {"business_goal": "test"},
        unresolved_questions=[],
        risk_list=risk_list if risk_list is not None else [],
        quality_score=quality_score,
        raw_llm_output="{}"
    )


class TestRunGateValidation(unittest.TestCase):
    def setUp(self):
        self.main_artifact = _make_artifact(quality_score=85)

    @patch("orchestrator.load_skill_gate")
    def test_no_gate_config_passes(self, mock_gate):
        mock_gate.return_value = None
        result = run_gate_validation(self.main_artifact, [], "skill_se_requirement")
        self.assertIsInstance(result, GateResult)
        self.assertTrue(result.passed)
        self.assertEqual(result.action, "continue")

    @patch("orchestrator.load_skill_gate")
    def test_pass_when_all_good(self, mock_gate):
        mock_gate.return_value = {
            "threshold_settings": {"quality_score_min": 70},
            "validation_rules": [],
            "failure_handling": {"action": "pause_workflow"},
        }
        result = run_gate_validation(self.main_artifact, [], "skill_se_requirement")
        self.assertTrue(result.passed)
        self.assertEqual(result.action, "continue")

    @patch("orchestrator.load_skill_gate")
    def test_fail_when_low_quality_score(self, mock_gate):
        mock_gate.return_value = {
            "threshold_settings": {"quality_score_min": 70},
            "validation_rules": [],
            "failure_handling": {"action": "pause_workflow"},
        }
        low = _make_artifact(quality_score=65)
        result = run_gate_validation(low, [], "skill_se_requirement")
        self.assertFalse(result.passed)
        self.assertIn("quality_score", result.message)
        self.assertEqual(result.action, "pause_workflow")

    @patch("orchestrator.load_skill_gate")
    def test_zero_quality_score_fails(self, mock_gate):
        mock_gate.return_value = {
            "threshold_settings": {"quality_score_min": 70},
            "validation_rules": [],
            "failure_handling": {"action": "pause_workflow"},
        }
        zero = _make_artifact(quality_score=0)
        result = run_gate_validation(zero, [], "skill_se_requirement")
        self.assertFalse(result.passed)


if __name__ == "__main__":
    unittest.main()
