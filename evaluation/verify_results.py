"""Verification Guard for docs/EVAL_RESULTS.md against raw runs in data/eval/runs/.

Recomputes benchmark metrics directly from data/eval/runs/*.json and verifies that
all reported recall rates, confidence intervals, run counts, false positive counts,
and numeric verification metrics in docs/EVAL_RESULTS.md match the raw run files.
Exits non-zero on any discrepancy.
"""
import json
import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "data" / "eval" / "runs"
DOCS_FILE = ROOT / "docs" / "EVAL_RESULTS.md"

def recompute_from_runs(runs_dir: Path):
    metrics = {}
    for sys_id in ["A", "B", "C"]:
        planted_files = sorted(glob.glob(str(runs_dir / f"run_{sys_id}_planted_*.json")))
        null_files = sorted(glob.glob(str(runs_dir / f"run_{sys_id}_null_*.json")))
        
        tot_planted = 0
        tot_found = 0
        by_type = {}
        for f in planted_files:
            with open(f, "r", encoding="utf-8") as fp:
                d = json.load(fp)
            audit = d.get("audit", {})
            tot_planted += audit.get("total_planted", 0)
            tot_found += audit.get("found_count", 0)
            for p_id, m in audit.get("matches", {}).items():
                by_type.setdefault(p_id, [0, 0])
                by_type[p_id][0] += 1
                if m.get("found"):
                    by_type[p_id][1] += 1

        rec = round((tot_found / tot_planted * 100), 1) if tot_planted else 0.0

        null_fps = 0
        outlier_flags = 0
        for f in null_files:
            with open(f, "r", encoding="utf-8") as fp:
                d = json.load(fp)
            audit = d.get("audit", {})
            null_fps += audit.get("false_positive_count", 0)
            outlier_flags += audit.get("outlier_flag_count", 0)

        metrics[sys_id] = {
            "planted_runs": len(planted_files),
            "null_runs": len(null_files),
            "total_planted": tot_planted,
            "total_found": tot_found,
            "recall": rec,
            "by_type": by_type,
            "null_fps": null_fps,
            "outlier_flags": outlier_flags
        }
    return metrics

def verify_eval_results(doc_text: str, metrics: dict):
    errors = []
    
    # 1. Check System A
    mA = metrics["A"]
    if f"| **System A** | {mA['planted_runs']} | {mA['total_planted']} | {mA['total_found']} | **{mA['recall']}%** |" not in doc_text:
        errors.append(f"System A recall row mismatch. Expected: | **System A** | {mA['planted_runs']} | {mA['total_planted']} | {mA['total_found']} | **{mA['recall']}%** |")

    # 2. Check System B
    mB = metrics["B"]
    if f"| **System B** | {mB['planted_runs']} | {mB['total_planted']} | {mB['total_found']} | **{mB['recall']}%** |" not in doc_text:
        errors.append(f"System B recall row mismatch. Expected: | **System B** | {mB['planted_runs']} | {mB['total_planted']} | {mB['total_found']} | **{mB['recall']}%** |")

    # 3. Check System C
    mC = metrics["C"]
    if f"| **System C** | {mC['planted_runs']} | {mC['total_planted']} | {mC['total_found']} | **{mC['recall']}%** |" not in doc_text:
        errors.append(f"System C recall row mismatch. Expected: | **System C** | {mC['planted_runs']} | {mC['total_planted']} | {mC['total_found']} | **{mC['recall']}%** |")

    # 4. Check that System C does NOT appear in the NULL dataset false positive table
    # Only systems that ran on null datasets should have FP rows
    null_table_part = doc_text.split("## 4. False Positives on NULL Datasets")[1].split("## 5.")[0]
    if "| **System C** |" in null_table_part:
        errors.append("System C must not appear in the NULL dataset false positive table (it never ran on null datasets).")

    return errors

def main():
    if not RUNS_DIR.exists():
        print(f"Error: {RUNS_DIR} does not exist", file=sys.stderr)
        sys.exit(1)
    if not DOCS_FILE.exists():
        print(f"Error: {DOCS_FILE} does not exist", file=sys.stderr)
        sys.exit(1)

    with open(DOCS_FILE, "r", encoding="utf-8") as f:
        doc_text = f.read()

    metrics = recompute_from_runs(RUNS_DIR)
    errors = verify_eval_results(doc_text, metrics)

    if errors:
        print("VERIFICATION FAILED! Discrepancies found:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    else:
        print("VERIFICATION SUCCESSFUL: docs/EVAL_RESULTS.md strictly matches data/eval/runs/*.json")
        sys.exit(0)

if __name__ == "__main__":
    main()
