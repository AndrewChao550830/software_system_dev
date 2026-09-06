#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resume Run CLI Tool
Harness AI Agent SE Workflow Command Line Utility
版本: 1.0.0
功能:
    list      列出所有已儲存 workflow run_id
    dump      匯出指定run全部artifact至JSON檔
    resume    繼續Gate暫停的Workflow，支援 approve / rerun / cancel
參數:
    --show-last     顯示上一次Gate攔截詳細資訊
    --quiet (-q)    安靜模式，跳過互動確認，適合批次自動化
    --fail-fast     遇到錯誤回傳非0 exit code，供CI/自動化流程判斷
    --version       顯示版本資訊
依賴: orchestrator.py (init_db, resume_workflow, load_workflow_spec, load_artifacts, list_all_run_ids)
"""
import argparse
import yaml
import json
import sys
from pathlib import Path
from orchestrator import (
    init_db,
    resume_workflow,
    load_workflow_spec,
    load_artifacts,
    list_all_run_ids
)

__VERSION__ = "1.0.0"


def dump_artifact(run_id: str, out_path: str):
    artifacts = load_artifacts(run_id)
    if not artifacts:
        print(f"❌ RunID {run_id} 沒有Artifact")
        sys.exit(1)
    serial_list = []
    for art in artifacts:
        serial_list.append({
            "run_id": run_id,
            "stage_id": art.stage_id,
            "skill_id": art.skill_id,
            "quality_score": art.quality_score,
            "artifact": art.artifact,
            "unresolved_questions": art.unresolved_questions,
            "risk_list": art.risk_list,
            "raw_llm_output": art.raw_llm_output
        })
    Path(out_path).write_text(json.dumps(serial_list, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Artifact已匯出至 {out_path}")


def print_last_gate_info(latest_art):
    """印出上一輪 Gate 攔截資訊"""
    print("\n📌 上一輪 Gate 攔截資訊")
    print("-"*70)
    risk_list = getattr(latest_art, "risk_list", [])
    unresolved = getattr(latest_art, "unresolved_questions", [])
    artifact_data = getattr(latest_art, "artifact", {})

    print(f"Stage ID     : {latest_art.stage_id}")
    print(f"Skill ID     : {latest_art.skill_id}")
    print(f"Quality Score: {latest_art.quality_score}")

    if risk_list:
        print("\n⚠️ 風險/阻斷漏洞清單：")
        for risk in risk_list:
            vuln_id = risk.get("vuln_id", "N/A")
            sev = risk.get("severity", "N/A")
            desc = risk.get("description", "N/A")
            print(f"  [{vuln_id}] {sev} | {desc}")

    if unresolved:
        print("\n❓ 待解決問題：")
        for item in unresolved:
            print(f" - {item}")

    if artifact_data:
        ac = artifact_data.get("acceptance_criteria", [])
        if ac:
            print("\n✅ 驗收準則：")
            for criteria in ac:
                print(f" - {criteria}")
    print("-"*70)


def main():
    parser = argparse.ArgumentParser(
        description="Harness SE Agent Workflow CLI｜Resume / List / Dump workflow runs",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--version", "-v", action="version", version=f"%(prog)s v{__VERSION__}", help="顯示版本資訊")
    subparsers = parser.add_subparsers(dest="command", required=True, help="可用子命令")

    # 子命令 resume
    resume_parser = subparsers.add_parser("resume", help="繼續已暫停的Run (approve/rerun/cancel)")
    resume_parser.add_argument("run_id", type=str, help="Workflow Run ID")
    resume_parser.add_argument("--action", "-a", required=True, choices=["approve", "rerun", "cancel"],
                              help="Gate動作: approve / rerun / cancel")
    resume_parser.add_argument("--wf", default="workflow_spec.yaml", help="Workflow spec yaml路徑，預設 workflow_spec.yaml")
    resume_parser.add_argument("--show-last", action="store_true", help="顯示上一輪Gate攔截詳細訊息")
    resume_parser.add_argument("--quiet", "-q", action="store_true", help="安靜模式，跳過互動確認，適合批次自動化")
    resume_parser.add_argument("--fail-fast", action="store_true", help="遇到例外直接退出並回傳非0 exit code，CI專用")

    # 子命令 list
    subparsers.add_parser("list", help="列出全部 Run ID")

    # 子命令 dump
    dump_parser = subparsers.add_parser("dump", help="將Run的Artifact匯出為JSON檔")
    dump_parser.add_argument("run_id", type=str, help="Workflow Run ID")
    dump_parser.add_argument("-o", "--output", default="artifacts_dump.json", help="輸出JSON檔名，預設 artifacts_dump.json")
    dump_parser.add_argument("--fail-fast", action="store_true", help="遇到例外直接退出並回傳非0 exit code，CI專用")

    args = parser.parse_args()

    try:
        init_db()

        if args.command == "list":
            run_ids = list_all_run_ids()
            print("📜 所有已儲存 Run ID：")
            for rid in run_ids:
                print(f" - {rid}")
            return

        elif args.command == "dump":
            dump_artifact(args.run_id, args.output)
            return

        elif args.command == "resume":
            wf_spec = load_workflow_spec(args.wf)
            artifacts = load_artifacts(args.run_id)
            if not artifacts:
                print(f"❌ RunID {args.run_id} 找不到任何artifact，確認run_id是否正確")
                if args.fail_fast:
                    sys.exit(1)
                return

            latest_art = artifacts[-1]

            # 若帶 --show-last，列印Gate資訊
            if args.show_last:
                print_last_gate_info(latest_art)

            project_context = getattr(latest_art, "project_context", {})
            user_input = getattr(latest_art, "user_input", "")
            paused_stage_id = getattr(latest_art, "stage_id", None)
            paused_skill_id = getattr(latest_art, "skill_id", None)

            print("="*70)
            print(f"Run ID        : {args.run_id}")
            print(f"Paused Stage  : {paused_stage_id}")
            print(f"Paused Skill  : {paused_skill_id}")
            print(f"Action        : {args.action}")
            print("="*70)

            # 判斷quiet模式，跳過y/N確認
            if not args.quiet:
                confirm = input("確認執行？(y/N) ").strip().lower()
                if confirm != "y":
                    print("已取消")
                    return
            else:
                print("🤖 Quiet mode: 略過互動確認，直接執行")

            result_artifacts = resume_workflow(
                run_id=args.run_id,
                wf_spec=wf_spec,
                gate_action=args.action,
                project_context=project_context,
                user_input=user_input
            )
            print(f"\n✅ Resume完成，總共輸出 {len(result_artifacts)} artifact")
            last = result_artifacts[-1]
            print(f"最後Artifact｜Stage:{last.stage_id}, Skill:{last.skill_id}, QualityScore:{last.quality_score}")

    except Exception as e:
        print(f"\n❌ 執行異常：{repr(e)}")
        if hasattr(args, "fail_fast") and args.fail_fast:
            sys.exit(1)
        return


if __name__ == "__main__":
    main()
