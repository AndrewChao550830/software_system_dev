import unittest
from orchestrator import gate_check, Artifact

class TestGateCheck(unittest.TestCase):
    def setUp(self):
        self.gate_config = {
            "quality_score_min": 70,
            "block_if_critical_vuln": True,
            "human_approval": True
        }

    def test_pass_when_all_good(self):
        # Main artifact with good quality score
        main_artifact = Artifact(
            skill_id="skill_se_requirement",
            stage_id="requirement",
            artifact={"business_goal": "test"},
            unresolved_questions=[],
            risk_list=[],
            quality_score=85,
            raw_llm_output="{}"
        )
        # No cross artifacts
        cross_artifacts = []
        pass_flag, msg = gate_check(main_artifact, cross_artifacts, self.gate_config)
        self.assertTrue(pass_flag)
        self.assertEqual(msg, "")

    def test_fail_when_low_quality_score(self):
        main_artifact = Artifact(
            skill_id="skill_se_requirement",
            stage_id="requirement",
            artifact={"business_goal": "test"},
            unresolved_questions=[],
            risk_list=[],
            quality_score=65,
            raw_llm_output="{}"
        )
        cross_artifacts = []
        pass_flag, msg = gate_check(main_artifact, cross_artifacts, self.gate_config)
        self.assertFalse(pass_flag)
        self.assertIn("quality_score", msg)

    def test_fail_when_security_blocking_vulnerabilities(self):
        main_artifact = Artifact(
            skill_id="skill_se_requirement",
            stage_id="requirement",
            artifact={"business_goal": "test"},
            unresolved_questions=[],
            risk_list=[],
            quality_score=85,
            raw_llm_output="{}"
        )
        # Security artifact with blocking vulnerabilities (inside artifact)
        sec_artifact = Artifact(
            skill_id="skill_se_sec_compliance",
            stage_id="requirement",
            artifact={"blocking_vulnerabilities": [{"vuln_id": "V1", "severity": "Critical", "description": "test vuln"}]},
            unresolved_questions=[],
            risk_list=[],
            quality_score=80,
            raw_llm_output="{}"
        )
        cross_artifacts = [sec_artifact]
        pass_flag, msg = gate_check(main_artifact, cross_artifacts, self.gate_config)
        self.assertFalse(pass_flag)
        self.assertIn("安全審計發現阻斷型漏洞", msg)

    def test_pass_when_security_no_blocking_vulnerabilities(self):
        main_artifact = Artifact(
            skill_id="skill_se_requirement",
            stage_id="requirement",
            artifact={"business_goal": "test"},
            unresolved_questions=[],
            risk_list=[],
            quality_score=85,
            raw_llm_output="{}"
        )
        # Security artifact with no blocking vulnerabilities
        sec_artifact = Artifact(
            skill_id="skill_se_sec_compliance",
            stage_id="requirement",
            artifact={"blocking_vulnerabilities": []},
            unresolved_questions=[],
            risk_list=[],
            quality_score=80,
            raw_llm_output="{}"
        )
        cross_artifacts = [sec_artifact]
        pass_flag, msg = gate_check(main_artifact, cross_artifacts, self.gate_config)
        self.assertTrue(pass_flag)
        self.assertEqual(msg, "")

    def test_fail_when_cost_control_critical_risk_no_mitigation(self):
        main_artifact = Artifact(
            skill_id="skill_se_requirement",
            stage_id="requirement",
            artifact={"business_goal": "test"},
            unresolved_questions=[],
            risk_list=[],
            quality_score=85,
            raw_llm_output="{}"
        )
        # Cost control artifact with a critical risk and no mitigation (in risk_list field of Artifact)
        cost_artifact = Artifact(
            skill_id="skill_se_cost_control",
            stage_id="requirement",
            artifact={},  # The artifact dictionary can be empty for this test
            unresolved_questions=[],
            risk_list=[{"risk_desc": "High cost due to inflation", "level": "Critical", "impact": "High", "mitigation": ""}],
            quality_score=80,
            raw_llm_output="{}"
        )
        cross_artifacts = [cost_artifact]
        pass_flag, msg = gate_check(main_artifact, cross_artifacts, self.gate_config)
        self.assertFalse(pass_flag)
        self.assertIn("成本控制發現阻斷型風險", msg)

    def test_pass_when_cost_control_critical_risk_with_mitigation(self):
        main_artifact = Artifact(
            skill_id="skill_se_requirement",
            stage_id="requirement",
            artifact={"business_goal": "test"},
            unresolved_questions=[],
            risk_list=[],
            quality_score=85,
            raw_llm_output="{}"
        )
        # Cost control artifact with a critical risk but with mitigation
        cost_artifact = Artifact(
            skill_id="skill_se_cost_control",
            stage_id="requirement",
            artifact={},
            unresolved_questions=[],
            risk_list=[{"risk_desc": "High cost due to inflation", "level": "Critical", "impact": "High", "mitigation": "Use fixed-price contracts"}],
            quality_score=80,
            raw_llm_output="{}"
        )
        cross_artifacts = [cost_artifact]
        pass_flag, msg = gate_check(main_artifact, cross_artifacts, self.gate_config)
        self.assertTrue(pass_flag)
        self.assertEqual(msg, "")

    def test_pass_when_cost_control_medium_risk_no_mitigation(self):
        main_artifact = Artifact(
            skill_id="skill_se_requirement",
            stage_id="requirement",
            artifact={"business_goal": "test"},
            unresolved_questions=[],
            risk_list=[],
            quality_score=85,
            raw_llm_output="{}"
        )
        # Cost control artifact with a medium risk and no mitigation (should not block)
        cost_artifact = Artifact(
            skill_id="skill_se_cost_control",
            stage_id="requirement",
            artifact={},
            unresolved_questions=[],
            risk_list=[{"risk_desc": "Medium cost due to training", "level": "Medium", "impact": "Medium", "mitigation": ""}],
            quality_score=80,
            raw_llm_output="{}"
        )
        cross_artifacts = [cost_artifact]
        pass_flag, msg = gate_check(main_artifact, cross_artifacts, self.gate_config)
        self.assertTrue(pass_flag)
        self.assertEqual(msg, "")

    def test_fail_when_both_security_and_cost_control_issues(self):
        main_artifact = Artifact(
            skill_id="skill_se_requirement",
            stage_id="requirement",
            artifact={"business_goal": "test"},
            unresolved_questions=[],
            risk_list=[],
            quality_score=85,
            raw_llm_output="{}"
        )
        sec_artifact = Artifact(
            skill_id="skill_se_sec_compliance",
            stage_id="requirement",
            artifact={"blocking_vulnerabilities": [{"vuln_id": "V1", "severity": "Critical", "description": "test vuln"}]},
            unresolved_questions=[],
            risk_list=[],
            quality_score=80,
            raw_llm_output="{}"
        )
        cost_artifact = Artifact(
            skill_id="skill_se_cost_control",
            stage_id="requirement",
            artifact={},
            unresolved_questions=[],
            risk_list=[{"risk_desc": "High cost due to inflation", "level": "Critical", "impact": "High", "mitigation": ""}],
            quality_score=80,
            raw_llm_output="{}"
        )
        cross_artifacts = [sec_artifact, cost_artifact]
        pass_flag, msg = gate_check(main_artifact, cross_artifacts, self.gate_config)
        self.assertFalse(pass_flag)
        self.assertIn("安全審計發現阻斷型漏洞", msg)
        self.assertIn("成本控制發現阻斷型風險", msg)

if __name__ == '__main__':
    unittest.main()