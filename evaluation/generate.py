"""Evaluation Dataset Generator (Stage B1).

Generates synthetic datasets with ground-truth planted statistical signals and NULL datasets:
- S1: Segment effect (Cohen's d ~ 0.8) between GroupA and GroupB on metric_score.
- C1: Correlation (Pearson r ~ 0.6) between var_x and var_y.
- T1: Monthly upward trend with known slope on trend_metric over date.
- O1: Outliers (2% of rows, ~10x scale) in volume.
- Q1: Sentinel value 999 in satisfaction_score (3% of rows).
- Q2: Impossible negative salary values in salary (approx 2% of rows).
- M1: 20% MCAR missingness in activity_index.
- Decoy columns: decoy_cat, decoy_num1, decoy_num2.
- NULL datasets: same schema, zero planted signal / stationary noise.

Outputs:
  CSV + companion manifest.json per seed under data/eval/datasets/
"""
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EVAL_DIR = ROOT / "data" / "eval"
DATASETS_DIR = EVAL_DIR / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)


def generate_dataset(
    seed: int,
    is_null: bool = False,
    n_rows: int = 2000
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Generate a single dataset (planted or null) with manifest."""
    rng = np.random.default_rng(seed)

    # 1. Base dates: 24 months spanning 2023-01 to 2024-12
    start_date = pd.Timestamp("2023-01-01")
    date_offsets = rng.integers(0, 730, size=n_rows)
    dates = [start_date + pd.Timedelta(days=int(d)) for d in date_offsets]
    dates.sort()

    record_ids = np.arange(1, n_rows + 1)

    # 2. Segments: GroupA (40%), GroupB (40%), GroupC (20%)
    segment_choices = ["GroupA", "GroupB", "GroupC"]
    segments = rng.choice(segment_choices, size=n_rows, p=[0.40, 0.40, 0.20])

    # 3. S1: Segment effect on metric_score (Cohen's d ~ 0.8)
    # Pooled SD = 15. Mean diff = 0.8 * 15 = 12.0
    if not is_null:
        metric_score = np.zeros(n_rows, dtype=float)
        for i, seg in enumerate(segments):
            if seg == "GroupA":
                metric_score[i] = rng.normal(loc=112.0, scale=15.0)
            elif seg == "GroupB":
                metric_score[i] = rng.normal(loc=100.0, scale=15.0)
            else:
                metric_score[i] = rng.normal(loc=103.0, scale=15.0)
        cohens_d = 0.80
    else:
        metric_score = rng.normal(loc=100.0, scale=15.0, size=n_rows)
        cohens_d = 0.0

    # 4. C1: Correlation between var_x and var_y (r ~ 0.6)
    var_x = rng.normal(loc=50.0, scale=10.0, size=n_rows)
    if not is_null:
        # r = 0.6 => y = r * x + sqrt(1 - r^2) * noise
        r_target = 0.60
        noise = rng.normal(loc=0.0, scale=10.0, size=n_rows)
        var_y = 50.0 + r_target * (var_x - 50.0) + np.sqrt(1 - r_target**2) * noise
    else:
        var_y = rng.normal(loc=50.0, scale=10.0, size=n_rows)

    # 5. T1: Monthly upward trend on trend_metric
    # Convert dates to months since start
    months = np.array([(d.year - 2023) * 12 + d.month for d in dates], dtype=float)
    if not is_null:
        slope = 2.5
        trend_metric = 100.0 + slope * months + rng.normal(loc=0.0, scale=8.0, size=n_rows)
    else:
        slope = 0.0
        trend_metric = 100.0 + rng.normal(loc=0.0, scale=8.0, size=n_rows)

    # 6. O1: Outliers in volume (2% of rows, ~10x scale)
    base_volume = rng.gamma(shape=5.0, scale=10.0, size=n_rows)  # mean 50
    if not is_null:
        outlier_indices = rng.choice(n_rows, size=int(n_rows * 0.02), replace=False)
        base_volume[outlier_indices] = base_volume[outlier_indices] * rng.uniform(8.0, 12.0, size=len(outlier_indices))
        outlier_rate = 0.02
    else:
        outlier_rate = 0.0

    # 7. Q1: Sentinel 999 in satisfaction_score (3% of rows)
    satisfaction_score = rng.integers(1, 10, size=n_rows).astype(float)
    if not is_null:
        sentinel_indices = rng.choice(n_rows, size=int(n_rows * 0.03), replace=False)
        satisfaction_score[sentinel_indices] = 999.0
        q1_count = len(sentinel_indices)
    else:
        q1_count = 0

    # 8. Q2: Impossible negative values in salary (approx 2% of rows)
    salary = rng.normal(loc=85000.0, scale=15000.0, size=n_rows)
    salary = np.maximum(salary, 35000.0)
    if not is_null:
        neg_indices = rng.choice(n_rows, size=int(n_rows * 0.02), replace=False)
        salary[neg_indices] = -1.0 * np.abs(rng.normal(loc=50000.0, scale=10000.0, size=len(neg_indices)))
        q2_count = len(neg_indices)
    else:
        q2_count = 0

    # 9. M1: 20% MCAR missingness in activity_index
    activity_index = rng.normal(loc=70.0, scale=12.0, size=n_rows)
    activity_col = pd.Series(activity_index, dtype=float)
    if not is_null:
        missing_indices = rng.choice(n_rows, size=int(n_rows * 0.20), replace=False)
        activity_col.iloc[missing_indices] = np.nan
        m1_rate = 0.20
    else:
        m1_rate = 0.0

    # 10. Decoy columns (no signal)
    decoy_cat = rng.choice(["Alpha", "Beta", "Gamma"], size=n_rows)
    decoy_num1 = rng.normal(loc=50.0, scale=10.0, size=n_rows)
    decoy_num2 = rng.uniform(low=0.0, high=100.0, size=n_rows)

    df = pd.DataFrame({
        "record_id": record_ids,
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "segment": segments,
        "metric_score": np.round(metric_score, 2),
        "var_x": np.round(var_x, 2),
        "var_y": np.round(var_y, 2),
        "trend_metric": np.round(trend_metric, 2),
        "volume": np.round(base_volume, 2),
        "satisfaction_score": satisfaction_score,
        "salary": np.round(salary, 2),
        "activity_index": np.round(activity_col, 2),
        "decoy_cat": decoy_cat,
        "decoy_num1": np.round(decoy_num1, 2),
        "decoy_num2": np.round(decoy_num2, 2)
    })

    # Manifest building
    planted_findings = {}
    if not is_null:
        planted_findings = {
            "S1": {
                "id": "S1",
                "type": "segment_difference",
                "segment_column": "segment",
                "metric_column": "metric_score",
                "groups": ["GroupA", "GroupB"],
                "target_effect_size": cohens_d,
                "direction": "GroupA > GroupB"
            },
            "C1": {
                "id": "C1",
                "type": "correlation",
                "column_1": "var_x",
                "column_2": "var_y",
                "target_r": 0.60,
                "direction": "positive"
            },
            "T1": {
                "id": "T1",
                "type": "trend",
                "date_column": "date",
                "metric_column": "trend_metric",
                "target_slope": 2.5,
                "direction": "upward"
            },
            "O1": {
                "id": "O1",
                "type": "outlier",
                "column": "volume",
                "rate": outlier_rate,
                "scale": "10x"
            },
            "Q1": {
                "id": "Q1",
                "type": "sentinel",
                "column": "satisfaction_score",
                "sentinel_value": 999.0,
                "count": q1_count
            },
            "Q2": {
                "id": "Q2",
                "type": "invalid_domain",
                "column": "salary",
                "condition": "negative_values",
                "count": q2_count
            },
            "M1": {
                "id": "M1",
                "type": "missingness",
                "column": "activity_index",
                "rate": m1_rate
            }
        }

    manifest = {
        "seed": seed,
        "is_null": is_null,
        "row_count": len(df),
        "columns": list(df.columns),
        "planted_findings": planted_findings
    }

    return df, manifest


def generate_benchmark_suite(
    planted_seeds: int = 10,
    null_seeds: int = 10,
    n_rows: int = 2000
) -> Dict[str, Any]:
    """Generate complete benchmark suite writing CSV + manifest.json."""
    generated_files = []

    # 1. Planted datasets
    for s in range(1, planted_seeds + 1):
        df, manifest = generate_dataset(seed=s, is_null=False, n_rows=n_rows)
        csv_path = DATASETS_DIR / f"planted_seed_{s}.csv"
        manifest_path = DATASETS_DIR / f"planted_seed_{s}_manifest.json"
        df.to_csv(csv_path, index=False)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        generated_files.append({"type": "planted", "seed": s, "csv": str(csv_path), "manifest": str(manifest_path)})

    # 2. NULL datasets
    for s in range(101, 101 + null_seeds):
        df, manifest = generate_dataset(seed=s, is_null=True, n_rows=n_rows)
        csv_path = DATASETS_DIR / f"null_seed_{s}.csv"
        manifest_path = DATASETS_DIR / f"null_seed_{s}_manifest.json"
        df.to_csv(csv_path, index=False)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        generated_files.append({"type": "null", "seed": s, "csv": str(csv_path), "manifest": str(manifest_path)})

    summary = {
        "status": "success",
        "planted_seeds_count": planted_seeds,
        "null_seeds_count": null_seeds,
        "total_datasets": len(generated_files),
        "row_count_each": n_rows,
        "output_directory": str(DATASETS_DIR),
        "datasets": generated_files
    }

    suite_manifest = DATASETS_DIR / "suite_manifest.json"
    with open(suite_manifest, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic evaluation datasets")
    parser.add_argument("--planted-seeds", type=int, default=10, help="Number of planted seeds (default 10)")
    parser.add_argument("--null-seeds", type=int, default=10, help="Number of null seeds (default 10)")
    parser.add_argument("--rows", type=int, default=2000, help="Row count per dataset (default 2000)")
    args = parser.parse_args()

    res = generate_benchmark_suite(
        planted_seeds=args.planted_seeds,
        null_seeds=args.null_seeds,
        n_rows=args.rows
    )
    print(f"Generated {res['total_datasets']} datasets under {res['output_directory']}")
