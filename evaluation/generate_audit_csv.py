"""Generate data/eval/numeric_audit.csv directly from raw run files and pandas recomputation."""
import json
import glob
import re
import os
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evaluation.metrics import compute_all_csv_statistics
EVAL_DIR = ROOT / "data" / "eval"
RUNS_DIR = EVAL_DIR / "runs"
DATASETS_DIR = EVAL_DIR / "datasets"
OUTPUT_CSV = EVAL_DIR / "numeric_audit.csv"

def generate_numeric_audit():
    rows = []
    # Audit Systems B and C (and A)
    for sys_id in ["A", "B", "C"]:
        files = sorted(glob.glob(str(RUNS_DIR / f"run_{sys_id}_*.json")))
        for fpath in files:
            run_id = Path(fpath).stem
            with open(fpath, "r", encoding="utf-8") as f:
                d = json.load(f)
            dataset_name = d.get("dataset", "")
            csv_path = DATASETS_DIR / dataset_name
            df = pd.read_csv(csv_path) if csv_path.exists() else None
            stats_pool = compute_all_csv_statistics(df) if df is not None else set()

            # Collect narrative text + chat answers
            full_text = d.get("executive_summary", "")
            for ca in d.get("chat_answers", []):
                full_text += " " + str(ca.get("answer", ""))

            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", full_text) if s.strip()]
            for s in sentences:
                tokens = re.findall(r"(?<![\w\.-])-?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?!\w)|(?<![\w\.-])-?\d+\.\d+(?!\w)", s)
                for t in tokens:
                    try:
                        num = float(t.replace(",", ""))
                    except ValueError:
                        continue

                    # Source claim extraction: context window around the number
                    idx = s.find(t)
                    start = max(0, idx - 30)
                    end = min(len(s), idx + len(t) + 30)
                    source_claim = s[start:end].strip()

                    res = "unverifiable"
                    recomp = "N/A"

                    if num in stats_pool or round(num, 2) in stats_pool or round(num, 1) in stats_pool or float(int(num)) in stats_pool:
                        res = "match"
                        recomp = str(num)
                    else:
                        for cand in stats_pool:
                            if abs(cand) > 0 and abs(num - cand) / abs(cand) <= 0.02:
                                res = "rounding"
                                recomp = str(round(cand, 4))
                                break
                            elif abs(num - cand) <= 0.05:
                                res = "rounding"
                                recomp = str(round(cand, 4))
                                break

                    rows.append({
                        "system": sys_id,
                        "run_id": run_id,
                        "sentence": s,
                        "number": t,
                        "source_claim": source_claim,
                        "pandas_recomputation": recomp,
                        "result": res
                    })

    df_out = pd.DataFrame(rows)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"Generated {len(df_out)} rows in {OUTPUT_CSV}")
    for sys_id in ["A", "B", "C"]:
        sub = df_out[df_out["system"] == sys_id]
        print(f"System {sys_id}: {len(sub)} total numbers")
        print(sub["result"].value_counts().to_dict())

if __name__ == "__main__":
    generate_numeric_audit()
