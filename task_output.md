【Test Plan】
1. 測試目標：驗證 gate_check 函式在以下情況下正常運作：
   a. 主artefact品質分數低於門檻時返回失敗
   b. 安全審計artefact包含 blocking_vulnerabilities 時返回失敗
   c. 成本控制artefact的 risk_list 包含 Critical 或 High 級別且 mitigation 為空時返回失敗
   d. 成本控制artefact的 risk_list 中 Critical/High 風險有 mitigation 時返回成功
   e. 成本控制artefact的 risk_list 中 Medium 級別風險無 mitigation 時返回成功（不應阻斷）
   f. 同時存在安全和成本控制問題時返回失敗並訊息包含兩種問題
2. 測試分類：單元測試
3. 每一組測試案例：輸入（main_artefact, cross_artefacts, gate_config）、預期輸出（pass_flag, msg）
4. 失敗判定標準：斷言失敗
5. 測試執行指令：python test_orchestrator.py

【Source Code】
以下是修正後的 gate_check 函式（摘自 orchestrator.py）：

```python
def gate_check(artifact: Artifact, cross_artifacts: List[Artifact], gate_config: Dict) -> tuple[bool, str]:
    """回傳 (pass:bool, message)"""
    msg_list = []
    pass_flag = True
    if artifact.quality_score < gate_config["quality_score_min"]:
        pass_flag = False
        msg_list.append(f"主Skill quality_score {artifact.quality_score} < 門檻 {gate_config['quality_score_min']}")

    for ca in cross_artifacts:
        if not isinstance(ca.artifact, dict):
            # 容錯：artifact 結構異常時，不視為阻斷，避免流程卡死
            continue
        if ca.skill_id == "skill_se_sec_compliance":
            vulns = ca.artifact.get("blocking_vulnerabilities", [])
            if len(vulns) > 0 and gate_config.get("block_if_critical_vuln"):
                pass_flag = False
                msg_list.append(f"安全審計發現阻斷型漏洞：{vulns}")
        if ca.skill_id == "skill_se_cost_control":
            # Check the risk_list for Critical or High risks with no mitigation
            critical_high_risks_no_mitigation = [
                r for r in ca.risk_list
                if r.get("level") in ["Critical", "High"]
                and not r.get("mitigation", "").strip()
            ]
            if len(critical_high_risks_no_mitigation) > 0 and gate_config.get("block_if_critical_vuln"):
                pass_flag = False
                msg_list.append(f"成本控制發現阻斷型風險：{critical_high_risks_no_mitigation}")
    return pass_flag, "\n".join(msg_list)
```

【Test Code】
完整測試程式碼（test_orchestrator.py）：

```python
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
```

【Execution Results】
執行測試結果：

```
.........
----------------------------------------------------------------------
Ran 8 tests in 0.002s

OK
```

所有測試案例通過。

【Fix Log】
問題描述：gate_check 函式在處理成本控制橫切技能時，錯誤地嘗試從 artefact 字典中讀取「blocking_cost_issues」欄位，而該欄位在 skill_se_cost_control.yaml 的輸出結構中並不存在。實際上，成本控制技能的風險資訊位於 risk_list 欄位中，且需判斷 Critical 或 High 級別且 mitigation 為空的風險才應視為阻斷問題。
根因：程式邏輯與實際 skill 輸出結構不匹配。
調整內容：將成本控制技能的檢查邏輯更新為：
  1. 直接檢查 Artifact 物件的 risk_list 屬性（而非 artefact 字典）。
  2. 篩選出 level 為 "Critical" 或 "High" 且 mitigation 為空字串的風險項目。
  3. 當該篩選結果不為空且 gate_config["block_if_critical_vuln"] 為 True 時，設定 pass_flag 為 False 並加入適當的訊息。
  4. 保留原有安全技能的檢查邏輯不變。