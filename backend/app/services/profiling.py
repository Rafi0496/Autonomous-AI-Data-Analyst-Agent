"""Data profiling pipeline: profile_dataset() standalone testable service.

Computes:
- Shape, column types, memory usage
- Per-column metrics: missing rates, cardinality, distributions, quantiles, outliers
- Data quality score (0 to 100) and actionable warnings
"""
from datetime import datetime
from typing import Any, Dict, List
import numpy as np
import pandas as pd
from shared.schemas.profile import ColumnProfile, DataQualitySummary, DatasetProfile

class DataProfilingService:
    @staticmethod
    def _infer_type(series: pd.Series) -> str:
        """Infer semantic column type."""
        if pd.api.types.is_bool_dtype(series):
            return "boolean"
        if pd.api.types.is_numeric_dtype(series):
            # Check if binary (0/1)
            unique_vals = set(series.dropna().unique())
            if unique_vals.issubset({0, 1}) and len(unique_vals) <= 2:
                return "boolean"
            return "numeric"
        if pd.api.types.is_datetime64_any_dtype(series):
            return "datetime"
            
        # Try datetime conversion on non-null sample
        sample = series.dropna().astype(str).head(30)
        if not sample.empty:
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    converted = pd.to_datetime(sample, errors="coerce", format="mixed")
                if converted.notnull().mean() > 0.8:
                    return "datetime"
            except Exception:
                pass
                
        # Categorical vs Free text based on cardinality
        num_unique = series.nunique()
        total = len(series)
        if total > 0 and (num_unique <= 50 or (num_unique / total) < 0.20):
            return "categorical"
            
        return "text"

    @classmethod
    def profile_dataset(cls, df: pd.DataFrame, dataset_id: str = "dataset") -> DatasetProfile:
        """Generate comprehensive deterministic profile of a DataFrame."""
        row_count, col_count = df.shape
        memory_usage_bytes = int(df.memory_usage(deep=True).sum())
        
        columns_profile: Dict[str, ColumnProfile] = {}
        total_missing = 0
        overall_warnings: List[str] = []

        for col in df.columns:
            series = df[col]
            null_count = int(series.isnull().sum())
            total_missing += null_count
            null_pct = round((null_count / row_count) * 100, 2) if row_count > 0 else 0.0
            
            unique_count = int(series.nunique(dropna=True))
            is_unique = (unique_count == row_count) and (null_count == 0)
            inferred = cls._infer_type(series)
            
            # Non-null samples (up to 5)
            sample_vals = [
                str(v) if isinstance(v, (pd.Timestamp, datetime)) else (float(v) if isinstance(v, (np.floating, float)) and not np.isnan(v) else v)
                for v in series.dropna().head(5).tolist()
            ]
            
            stats: Dict[str, Any] = {}
            col_warnings: List[str] = []

            if null_pct > 30.0:
                col_warnings.append(f"High missingness ({null_pct}% null)")
            if unique_count == 1:
                col_warnings.append("Zero variance (constant column)")
            if inferred == "categorical" and unique_count > 100:
                col_warnings.append(f"High cardinality categorical ({unique_count} distinct values)")

            if inferred == "numeric":
                num_series = pd.to_numeric(series, errors="coerce").dropna()
                if not num_series.empty:
                    q25 = float(num_series.quantile(0.25))
                    q75 = float(num_series.quantile(0.75))
                    iqr = q75 - q25
                    lower_bound = q25 - 1.5 * iqr
                    upper_bound = q75 + 1.5 * iqr
                    outliers_count = int(((num_series < lower_bound) | (num_series > upper_bound)).sum())
                    
                    stats = {
                        "min": float(num_series.min()),
                        "max": float(num_series.max()),
                        "mean": round(float(num_series.mean()), 2),
                        "std": round(float(num_series.std()), 2) if len(num_series) > 1 else 0.0,
                        "median": round(float(num_series.median()), 2),
                        "q25": round(q25, 2),
                        "q75": round(q75, 2),
                        "outliers_count": outliers_count
                    }
                    if outliers_count > 0:
                        col_warnings.append(f"{outliers_count} statistical outlier(s) detected via IQR.")
            elif inferred == "categorical":
                val_counts = series.value_counts(dropna=True).head(5)
                top_items = [{"value": str(k), "count": int(v), "percentage": round((v / row_count) * 100, 2)}
                             for k, v in val_counts.items()]
                stats = {"top_values": top_items}
            elif inferred == "datetime":
                dt_series = pd.to_datetime(series, errors="coerce").dropna()
                if not dt_series.empty:
                    stats = {
                        "min_date": dt_series.min().isoformat(),
                        "max_date": dt_series.max().isoformat(),
                        "timespan_days": int((dt_series.max() - dt_series.min()).days)
                    }

            columns_profile[str(col)] = ColumnProfile(
                name=str(col),
                original_dtype=str(series.dtype),
                inferred_type=inferred,
                null_count=null_count,
                null_percentage=null_pct,
                unique_count=unique_count,
                is_unique=is_unique,
                sample_values=sample_vals,
                stats=stats,
                warnings=col_warnings
            )
            
            if col_warnings:
                overall_warnings.extend([f"Column '{col}': {w}" for w in col_warnings])

        # Overall summary & quality score
        total_cells = row_count * col_count
        missing_pct = round((total_missing / total_cells) * 100, 2) if total_cells > 0 else 0.0
        duplicate_rows = int(df.duplicated().sum())
        dup_pct = round((duplicate_rows / row_count) * 100, 2) if row_count > 0 else 0.0
        
        # Retrieve raw and post-cleaning completeness scores and sampling disclosure if available
        raw_score = df.attrs.get("quality_score") or df.attrs.get("raw_quality_score")
        clean_score = df.attrs.get("post_cleaning_completeness") or df.attrs.get("cleaned_quality_score")
        sampling_disclosure = df.attrs.get("sampling_disclosure")

        cl_report = df.attrs.get("cleaning_report")
        if isinstance(cl_report, dict):
            if raw_score is None:
                raw_score = cl_report.get("quality_score") or cl_report.get("raw_quality_score")
            if clean_score is None:
                clean_score = cl_report.get("post_cleaning_completeness") or cl_report.get("cleaned_quality_score")
            if sampling_disclosure is None:
                sampling_disclosure = cl_report.get("sampling_disclosure")

        # Fallback raw quality score computation if uncleaned/standalone df
        if raw_score is None:
            penalty = (missing_pct * 0.7) + (dup_pct * 1.0) + (len(overall_warnings) * 1.5)
            raw_score = max(0.0, round(100.0 - penalty, 1))
            clean_score = raw_score

        quality_score = raw_score

        if duplicate_rows > 0:
            overall_warnings.insert(0, f"Detected {duplicate_rows} duplicate rows ({dup_pct}%).")
        if missing_pct > 10.0:
            overall_warnings.insert(0, f"Overall missingness is elevated at {missing_pct}%.")

        quality_summary = DataQualitySummary(
            total_cells=total_cells,
            missing_cells=total_missing,
            missing_percentage=missing_pct,
            duplicate_rows=duplicate_rows,
            duplicate_percentage=dup_pct,
            quality_score=quality_score,
            raw_quality_score=raw_score,
            post_cleaning_completeness=clean_score,
            cleaned_quality_score=clean_score,
            sampling_disclosure=sampling_disclosure,
            warnings=overall_warnings
        )

        return DatasetProfile(
            dataset_id=dataset_id,
            row_count=row_count,
            column_count=col_count,
            memory_usage_bytes=memory_usage_bytes,
            columns=columns_profile,
            quality_summary=quality_summary,
            created_at=datetime.utcnow().isoformat()
        )

profile_dataset = DataProfilingService.profile_dataset
