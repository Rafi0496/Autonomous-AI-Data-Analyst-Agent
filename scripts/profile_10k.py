"""cProfile 10k rows autonomous pipeline execution."""
import os
import cProfile
import pstats
import io
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))
os.environ["LLM_PROVIDER"] = "heuristic"

from backend.app.core.config import settings
from backend.app.services.cleaning import clean_data
from backend.app.agent.orchestrator import PlanActReflectOrchestrator
from evaluation.generate import generate_dataset

def run_10k_pipeline():
    df, manifest = generate_dataset(seed=42, is_null=False, n_rows=10000)
    ds_id = "scale_profile_10k"
    clean_path = settings.PROCESSED_DIR / f"{ds_id}_cleaned.csv"
    cleaned_df, clean_res = clean_data(df=df, dataset_id=ds_id, output_path=clean_path)
    orch = PlanActReflectOrchestrator(max_steps=3, token_budget=20000, provider="heuristic")
    res = orch.run_analysis(dataset_id=ds_id, goal="Profile 10k scale analysis.")
    return res

if __name__ == "__main__":
    pr = cProfile.Profile()
    pr.enable()
    run_10k_pipeline()
    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumtime")
    print("=" * 80)
    print("TOP 10 BY CUMULATIVE TIME (cumtime) FOR 10K ROWS:")
    print("=" * 80)
    ps.print_stats(10)
    print(s.getvalue())

    s2 = io.StringIO()
    ps2 = pstats.Stats(pr, stream=s2).sort_stats("tottime")
    print("=" * 80)
    print("TOP 10 BY TOTAL TIME (tottime) FOR 10K ROWS:")
    print("=" * 80)
    ps2.print_stats(10)
    print(s2.getvalue())
