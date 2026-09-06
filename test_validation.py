#!/usr/bin/env python3
"""
簡單的驗證腳本，用於檢查我們對Harness AI Skill Framework所做的變更是否語法正確且可載入
"""

import sys
import yaml
import os
from pathlib import Path

def test_yaml_loading(file_path, description):
    """測試YAML檔案是否可以正確載入"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        print(f"✅ {description}: 載入成功")
        return True
    except Exception as e:
        print(f"❌ {description}: 載入失敗 - {str(e)}")
        return False

def test_python_syntax(file_path, description):
    """測試Python檔案的語法是否正確"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            compile(f.read(), file_path, 'exec')
        print(f"✅ {description}: 語法正確")
        return True
    except SyntaxError as e:
        print(f"❌ {description}: 語法錯誤 - {str(e)}")
        return False
    except Exception as e:
        print(f"❌ {description}: 其他錯誤 - {str(e)}")
        return False

def test_skill_loading(skill_id, skill_dir="./skills"):
    """測試特定skill是否可以被orchestrator載入"""
    try:
        # 這裡我們只測試檔案存在且YAML有效，不實際執行orchestrator的load_skill函數
        skill_path = Path(skill_dir) / f"{skill_id}.yaml"
        if skill_path.exists():
            with open(skill_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            # 檢查是否有必要的結構
            if 'skillDefinition' in data or ('spec' in data and 'skillDefinition' in data['spec']):
                print(f"✅ Skill {skill_id}: 結構正確")
                return True
            else:
                print(f"❌ Skill {skill_id}: 缺少skillDefinition結構")
                return False
        else:
            print(f"❌ Skill {skill_id}: 檔案不存在")
            return False
    except Exception as e:
        print(f"❌ Skill {skill_id}: 載入失敗 - {str(e)}")
        return False

def main():
    print("=== 開始驗證我們的變更 ===\n")

    base_path = Path.cwd()
    all_passed = True

    # 1. 測試新建的skill_code_renderer.yaml
    print("1. 測試YAML檔案載入:")
    all_passed &= test_yaml_loading(
        base_path / "skills" / "skill_code_renderer.yaml",
        "skill_code_renderer.yaml"
    )

    # 2. 測試更新後的workflow_spec.yaml
    all_passed &= test_yaml_loading(
        base_path / "workflow_spec.yaml",
        "workflow_spec.yaml"
    )

    # 3. 測試orchestrator.py語法
    print("\n2. 測試Python語法:")
    all_passed &= test_python_syntax(
        base_path / "orchestrator.py",
        "orchestrator.py"
    )

    # 4. 測試關鍵skill是否可以被載入
    print("\n3. 測試關鍵Skill載入:")
    all_passed &= test_skill_loading("skill_code_renderer")
    all_passed &= test_skill_loading("skill_se_code_implementation")
    all_passed &= test_skill_loading("my-code-standard",
                                   skill_dir=str(Path.home() / ".claude" / "skills"))

    # 5. 驗證workflow_spec.yaml中的依賴關係
    print("\n4. 驗證工作流程依賴關係:")
    try:
        with open(base_path / "workflow_spec.yaml", 'r', encoding='utf-8') as f:
            workflow_data = yaml.safe_load(f)

        stages = {s['stage_id']: s for s in workflow_data.get('stages', [])}

        # 檢查code_renderer是否存在
        if 'code_renderer' in stages:
            print("✅ code_renderer階段存在")
            # 檢查其依賴
            deps = stages['code_renderer'].get('depends_on', [])
            if 'code_implementation' in deps:
                print("✅ code_renderer 正確依賴於 code_implementation")
            else:
                print(f"❌ code_renderer 依賴關係錯誤: {deps}")
                all_passed = False
        else:
            print("❌ code_renderer階段不存在")
            all_passed = False

        # 檢獡test_validation的依賴是否更新
        if 'test_validation' in stages:
            print("✅ test_validation階段存在")
            deps = stages['test_validation'].get('depends_on', [])
            if 'code_renderer' in deps and 'requirement' in deps:
                print("✅ test_validation 正確依賴於 requirement 和 code_renderer")
            else:
                print(f"❌ test_validation 依賴關係錯誤: {deps}")
                all_passed = False
        else:
            print("❌ test_validation階段不存在")
            all_passed = False

    except Exception as e:
        print(f"❌ 驗證工作流程依賴關係時發生錯誤: {str(e)}")
        all_passed = False

    print(f"\n=== 驗證完成 ===")
    if all_passed:
        print("🎉 所有驗證項目通過！變更看起來是正確的。")
        return 0
    else:
        print("⚠️  有驗證項目失敗，請檢查上述錯誤訊息。")
        return 1

if __name__ == "__main__":
    sys.exit(main())