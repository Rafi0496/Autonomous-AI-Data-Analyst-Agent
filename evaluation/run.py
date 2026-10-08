"""Evaluation Runner (Stage B3).

Executes benchmark evaluation across systems:
- System A: heuristic
- System B: gemini (full pipeline with citation checker enabled)
- System C: gemini_no_citations (Gemini with citation checker DISABLED, ablation)
- System D: claude (Claude only if ANTHROPIC_API_KEY is present, else 'NOT RUN (no key)')

Flags:
  --systems A,B,C,D (default: A,B,C,D)
  --seeds planted_count,null_count (default: 10,10 for A; 5,5 for B; 3 for C)
  --quick: fast run mode (1 planted, 1 null seed)
"""
import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.core.database import SessionLocal
from backend.app.core.config import settings
from backend.app.services.cleaning import clean_data
from backend.app.services.storage import StorageService
from backend.app.agent.llm_client import get_llm_client, HeuristicClient, GeminiClient
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from backend.app.services.chat_service import process_chat_question
from evaluation.match import audit_dataset_findings

EVAL_DIR = ROOT / "data" / "eval"
RUNS_DIR = EVAL_DIR / "runs"
DATASETS_DIR = EVAL_DIR / "datasets"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


def load_dataset_and_manifest(csv_name: str) -> Tuple[pd.DataFrame, Dict[str, Any], Path]:
    csv_path = DATASETS_DIR / csv_name
    manifest_path = DATASETS_DIR / csv_name.replace(".csv", "_manifest.json")
    if not csv_path.exists() or not manifest_path.exists():
        raise FileNotFoundError(f"Missing {csv_path} or {manifest_path}")

    df = pd.read_csv(csv_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    return df, manifest, csv_path


def run_pipeline_on_dataset(
    system_id: str,
    csv_name: str,
    db: SessionLocal,
    disable_citation_checker: bool = False,
    throttle_seconds: float = 3.0
) -> Dict[str, Any]:
    """Execute analysis pipeline and evaluation on a single dataset."""
    df, manifest, csv_path = load_dataset_and_manifest(csv_name)
    dataset_stem = Path(csv_name).stem
    is_null = manifest.get("is_null", False)
    seed = manifest.get("seed", 0)

    # 1. Clean data and save processed files
    output_clean_path = settings.PROCESSED_DIR / f"{dataset_stem}_cleaned.csv"
    cleaned_df, cl_res = clean_data(df, dataset_id=dataset_stem, output_path=output_clean_path)

    # 2. Setup Client
    if system_id == "A":
        client = get_llm_client("heuristic")
        prov_label = "heuristic"
    elif system_id in ("B", "C"):
        client = get_llm_client("gemini", allow_heuristic_fallback=False)
        prov_label = "gemini"
    elif system_id == "D":
        if not os.getenv("ANTHROPIC_API_KEY"):
            return {
                "system": "D",
                "status": "NOT RUN (no key)",
                "dataset": csv_name,
                "note": "ANTHROPIC_API_KEY is not configured"
            }
        client = get_llm_client("claude", allow_heuristic_fallback=False)
        prov_label = "claude"
    else:
        raise ValueError(f"Unknown system {system_id}")

    # Patch citation checker if System C (ablation)
    orig_validate = None
    if disable_citation_checker:
        import backend.app.agent.orchestrator as orch_mod
        orig_validate = orch_mod.validate_citations
        orch_mod.validate_citations = lambda synthesis_result, structured_results, dataset_profile, insights: {
            "is_valid": True,
            "total_claims_checked": 0,
            "verified_claims_count": 0,
            "unverified_claims_count": 0,
            "verification_rate_percent": 100.0,
            "number_verification_rate": 100.0,
            "claim_presence_rate": 100.0,
            "present_claims": [],
            "missing_claims": [],
            "pre_strip_verification_rate": 100.0,
            "post_strip_verification_rate": 100.0,
            "verified_numbers": [],
            "unverified_numbers": [],
            "unverified_claims": [],
            "stripped_sentences": [],
            "cleaned_executive_summary": synthesis_result.get("executive_summary", ""),
            "status": "passed_disabled"
        }

    # 3. Execute Autonomous Agent Run with retries for rate limits
    orch = PlanActReflectOrchestrator(
        max_steps=4,
        token_budget=35000,
        llm_client=client
    )

    t0 = time.time()
    agent_result = None
    retries = 3
    for attempt in range(retries):
        try:
            agent_result = orch.run_analysis(
                dataset_id=dataset_stem,
                goal="Identify significant segment differentials, metric correlations, temporal trends, volume outliers, and data quality issues."
            )
            break
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                wait_sec = 5.0 * (attempt + 1)
                print(f"Rate limit hit for {system_id} on {csv_name}. Retrying in {wait_sec}s...")
                time.sleep(wait_sec)
            else:
                print(f"Agent execution error on {csv_name}: {e}")
                break

    if disable_citation_checker and orig_validate is not None:
        import backend.app.agent.orchestrator as orch_mod
        orch_mod.validate_citations = orig_validate

    wall_time = time.time() - t0

    if not agent_result:
        agent_result = {
            "status": "failed",
            "insights": [],
            "synthesis": {"executive_summary": ""},
            "tokens_consumed": 0,
            "total_steps_executed": 0,
            "run_log": []
        }

    # 4. Run Chat Questions
    chat_answers = []
    questions = [
        "Is there a significant difference in metric_score across segment?",
        "What is the correlation between var_x and var_y?"
    ]
    for q in questions:
        try:
            c_res = process_chat_question(
                db=db,
                job_id="",
                question=q,
                dataset_id=dataset_stem
            )
            chat_answers.append({
                "question": q,
                "answer": c_res.get("answer"),
                "is_valid": (c_res.get("verification") or {}).get("is_valid", False)
            })
        except Exception as e:
            chat_answers.append({"question": q, "answer": f"ERROR: {e}", "is_valid": False})

    # 5. Match Ground-Truth Findings
    audit_res = audit_dataset_findings(
        manifest=manifest,
        insights=agent_result.get("insights", []),
        dq_caveats=agent_result.get("data_quality_insights", [])
    )

    # 6. Throttle for API rate limits
    if throttle_seconds > 0 and system_id in ("B", "C", "D"):
        time.sleep(throttle_seconds)

    record = {
        "system": system_id,
        "provider": prov_label,
        "model": getattr(client, "model", getattr(client, "model_name", "heuristic")),
        "dataset": csv_name,
        "seed": seed,
        "is_null": is_null,
        "wall_time_seconds": round(wall_time, 2),
        "tokens_consumed": agent_result.get("tokens_consumed", 0),
        "steps_executed": agent_result.get("total_steps_executed", 0),
        "tools_called": [s.get("tool") for s in agent_result.get("run_log", [])],
        "executive_summary": agent_result.get("synthesis", {}).get("executive_summary", ""),
        "chat_answers": chat_answers,
        "audit": audit_res
    }

    # Save raw per-run JSON
    run_file = RUNS_DIR / f"run_{system_id}_{dataset_stem}.json"
    with open(run_file, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    return record


def run_evaluation_suite(
    systems: List[str],
    quick_mode: bool = False
) -> Dict[str, Any]:
    """Execute complete evaluation suite across requested systems."""
    db = SessionLocal()
    suite_results = {}

    for sys_id in systems:
        print(f"\n{'=' * 70}")
        print(f"  RUNNING EVALUATION: SYSTEM {sys_id}")
        print(f"{'=' * 70}")

        if sys_id == "D" and not os.getenv("ANTHROPIC_API_KEY"):
            print("System D (Claude): NOT RUN (no key)")
            suite_results["D"] = {"system": "D", "status": "NOT RUN (no key)", "runs": []}
            continue

        # Determine datasets to run
        if quick_mode:
            target_datasets = ["planted_seed_1.csv", "null_seed_101.csv"]
        else:
            if sys_id == "A":
                # 10 planted + 10 null
                target_datasets = [f"planted_seed_{s}.csv" for s in range(1, 11)] + [f"null_seed_{s}.csv" for s in range(101, 111)]
            elif sys_id == "B":
                # 5 planted + 5 null (free-tier quota safety)
                target_datasets = [f"planted_seed_{s}.csv" for s in range(1, 6)] + [f"null_seed_{s}.csv" for s in range(101, 106)]
            elif sys_id == "C":
                # 3 planted seeds for ablation
                target_datasets = [f"planted_seed_{s}.csv" for s in range(1, 4)]
            else:
                target_datasets = ["planted_seed_1.csv"]

        system_runs = []
        is_ablation = (sys_id == "C")

        for ds_name in target_datasets:
            print(f"  [{sys_id}] Processing {ds_name}...")
            try:
                rec = run_pipeline_on_dataset(
                    system_id=sys_id,
                    csv_name=ds_name,
                    db=db,
                    disable_citation_checker=is_ablation,
                    throttle_seconds=3.0 if sys_id in ("B", "C") else 0.0
                )
                system_runs.append(rec)
                recall = rec.get("audit", {}).get("recall_percent", 0.0)
                fps = rec.get("audit", {}).get("false_positive_count", 0)
                print(f"       Done ({rec.get('wall_time_seconds')}s) | Recall: {recall}% | False Positives: {fps}")
            except Exception as e:
                print(f"       ERROR on {ds_name}: {e}")

        # Summary for system
        planted_runs = [r for r in system_runs if not r.get("is_null")]
        null_runs = [r for r in system_runs if r.get("is_null")]

        total_planted = sum(r.get("audit", {}).get("total_planted", 0) for r in planted_runs)
        total_found = sum(r.get("audit", {}).get("found_count", 0) for r in planted_runs)
        overall_recall = round((total_found / total_planted) * 100, 2) if total_planted > 0 else 0.0
        total_fps = sum(r.get("audit", {}).get("false_positive_count", 0) for r in null_runs)

        sys_summary = {
            "system": sys_id,
            "total_runs": len(system_runs),
            "planted_runs_count": len(planted_runs),
            "null_runs_count": len(null_runs),
            "planted_findings_total": total_planted,
            "planted_findings_found": total_found,
            "overall_recall_percent": overall_recall,
            "total_null_false_positives": total_fps,
            "runs": system_runs
        }

        # Save committed summary JSON
        summary_file = EVAL_DIR / f"summary_system_{sys_id}.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(sys_summary, f, indent=2)

        suite_results[sys_id] = sys_summary

    db.close()
    return suite_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run evaluation harness across systems")
    parser.add_argument("--systems", default="A,B,C,D", help="Comma-separated system IDs (A,B,C,D)")
    parser.add_argument("--quick", action="store_true", help="Quick mode (1 planted, 1 null seed per system)")
    args = parser.parse_args()

    systems_list = [s.strip().upper() for s in args.systems.split(",") if s.strip()]
    results = run_evaluation_suite(systems=systems_list, quick_mode=args.quick)
    print("\nEvaluation Suite Finished Successfully.")
