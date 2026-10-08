"""Script to dump and audit every number marked wrong for Systems B and C.
Extracts: (number, sentence, source, pandas recomputation).
Classifies into:
- genuinely wrong
- auditor cannot recompute
- rounding
"""
import os
import sys
import json
import re
from pathlib import Path
import pandas as pd
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evaluation.metrics import extract_numbers_from_text, compute_all_csv_statistics

RUNS_DIR = ROOT / "data" / "eval" / "runs"
DATASETS_DIR = ROOT / "data" / "eval" / "datasets"

def run_audit():
    results = []
    
    for sys_id in ["B", "C"]:
        run_files = sorted(list(RUNS_DIR.glob(f"run_{sys_id}_*.json")))
        for rf in run_files:
            with open(rf, "r", encoding="utf-8") as f:
                run_data = json.load(f)
            
            dataset_name = run_data.get("dataset")
            csv_path = DATASETS_DIR / dataset_name
            if not csv_path.exists():
                continue
            df = pd.read_csv(csv_path)
            stats_pool = compute_all_csv_statistics(df)
            
            # Extract texts with sentences
            texts_to_check = []
            exec_summary = run_data.get("executive_summary", "")
            if exec_summary:
                texts_to_check.append(("executive_summary", exec_summary))
            for ca in run_data.get("chat_answers", []):
                ans = str(ca.get("answer", ""))
                q = str(ca.get("question", ""))
                texts_to_check.append((f"chat: {q}", ans))
                
            for source_label, text in texts_to_check:
                # Split text into sentences
                sentences = re.split(r"(?<=[.!?])\s+", text)
                for sent in sentences:
                    nums = extract_numbers_from_text(sent)
                    for num in nums:
                        # Check match against current stats_pool
                        matched = False
                        rounded = round(num, 2)
                        if rounded in stats_pool or round(num, 1) in stats_pool or float(int(num)) in stats_pool:
                            matched = True
                        else:
                            for cand in stats_pool:
                                if abs(cand) > 0 and abs(num - cand) / abs(cand) <= 0.02:
                                    matched = True
                                    break
                                elif abs(num - cand) <= 0.05:
                                    matched = True
                                    break
                        if not matched:
                            results.append({
                                "system": sys_id,
                                "run_file": rf.name,
                                "dataset": dataset_name,
                                "source": source_label,
                                "number": num,
                                "sentence": sent.strip(),
                            })
                            
    print(f"Total numbers marked wrong across Systems B & C: {len(results)}")
    for r in results:
        print("--------------------------------------------------")
        print(f"System: {r['system']} | File: {r['run_file']} | Number: {r['number']}")
        print(f"Source: {r['source']}")
        print(f"Sentence: {r['sentence']}")
        
if __name__ == "__main__":
    run_audit()
