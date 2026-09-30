"""Print full segment_compare output for all 3 messy datasets, after cleaning.

Demonstrates that the casing normalization in clean_data() eliminates duplicate
segments like 'Electronics' / 'electronics' before segment comparison runs.
"""
import sys
import json
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
from backend.app.services.cleaning import clean_data
from backend.app.services.segmentation import segment_compare
from backend.app.services.storage import StorageService
from shared.schemas.dataset import DatasetCleaningOptions

DATASETS = [
    {
        "filename": "retail_sales_messy.csv",
        "dataset_id": "retail_sales_messy",
        "segment_column": "Category",
        "metric_column": "Unit_Price",
    },
    {
        "filename": "hr_attrition_messy.csv",
        "dataset_id": "hr_attrition_messy",
        "segment_column": "Department",
        "metric_column": "Annual_Salary",
    },
    {
        "filename": "marketing_campaign_messy.csv",
        "dataset_id": "marketing_campaign_messy",
        "segment_column": "Channel",
        "metric_column": "Ad_Spend",
    },
]

SAMPLES_DIR = ROOT / "data" / "samples"
PROCESSED_DIR = ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def main():
    for ds in DATASETS:
        print(f"\n{'='*70}")
        print(f"  DATASET: {ds['filename']}")
        print(f"{'='*70}")

        # Load raw
        raw_df = pd.read_csv(SAMPLES_DIR / ds["filename"])
        print(f"\n  [RAW] Unique values in '{ds['segment_column']}':")
        raw_vals = raw_df[ds["segment_column"]].dropna().unique().tolist()
        for v in sorted(str(x) for x in raw_vals):
            print(f"    - '{v}'")

        # Clean
        cleaned_df, result = clean_data(
            df=raw_df,
            dataset_id=ds["dataset_id"],
            output_path=PROCESSED_DIR / f"{ds['dataset_id']}_cleaned.csv",
            options=DatasetCleaningOptions(drop_duplicates=True, strip_whitespace=True),
        )

        print(f"\n  [CLEANED] Unique values in '{ds['segment_column']}':")
        clean_vals = cleaned_df[ds["segment_column"]].dropna().unique().tolist()
        for v in sorted(str(x) for x in clean_vals):
            print(f"    - '{v}'")

        if any(log.step == "normalize_categorical_casing" for log in result.logs):
            norm_log = [l for l in result.logs if l.step == "normalize_categorical_casing"][0]
            print(f"\n  [CLEANING LOG] Casing normalized in: {norm_log.affected_columns}")

        # Run segment_compare on the cleaned file
        print(f"\n  [SEGMENT COMPARE] {ds['segment_column']} x {ds['metric_column']}")
        try:
            seg_result = segment_compare(
                dataset_id=f"{ds['dataset_id']}_cleaned",
                segment_column=ds["segment_column"],
                metric_column=ds["metric_column"],
            )
            print(f"    Status: {seg_result['status']}")
            print(f"    Total records: {seg_result['total_records']}")
            print(f"    n_used: {seg_result.get('n_used')}")
            print(f"    n_excluded_imputed: {seg_result.get('n_excluded_imputed')}")
            print(f"    Total segments: {seg_result['total_segments']}")
            print(f"    Overall mean: {seg_result['overall_mean']}")
            print(f"    ANOVA p-value: {seg_result['anova_p_value']}")
            print(f"    Statistically significant: {seg_result['is_statistically_significant']}")
            if seg_result.get("top_segment"):
                t = seg_result["top_segment"]
                print(f"    Top segment: {t['segment']} (mean={t['mean']}, count={t['count']}, share={t['share_of_total_percent']}%)")
            if seg_result.get("bottom_segment"):
                b = seg_result["bottom_segment"]
                print(f"    Bottom segment: {b['segment']} (mean={b['mean']}, count={b['count']}, share={b['share_of_total_percent']}%)")
            print(f"    Top vs bottom ratio: {seg_result['top_vs_bottom_ratio']}")
            print(f"\n    All segments:")
            for seg in seg_result["segments"]:
                print(f"      {seg['segment']:20s}  count={seg['count']:3d}  mean={seg['mean']:10.2f}  median={seg['median']:10.2f}  share={seg['share_of_total_percent']:6.2f}%")
        except Exception as e:
            print(f"    ERROR: {e}")

    print(f"\n{'='*70}")
    print("  DONE — All 3 datasets processed successfully")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
