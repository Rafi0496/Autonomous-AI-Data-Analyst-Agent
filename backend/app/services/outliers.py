"""Statistical outlier detection tool: detect_outliers().

Supports:
- IQR (Interquartile Range)
- Z-score (standard score)
- Isolation Forest (multivariate unsupervised anomaly detection)
"""
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from backend.app.services.data_loader import get_dataset_dataframe

def detect_outliers(
    dataset_id: str,
    method: str = "iqr",
    columns: Optional[List[str]] = None,
    threshold: float = 1.5
) -> Dict[str, Any]:
    """
    Detect statistical outliers across numeric columns using IQR, Z-Score, or Isolation Forest.
    """
    df = get_dataset_dataframe(dataset_id)
    
    if columns:
        valid_cols = [c for c in columns if c in df.columns]
    else:
        valid_cols = df.columns.tolist()
        
    num_df = df[valid_cols].select_dtypes(include=[np.number])
    
    # Check if object cols can be converted
    for c in valid_cols:
        if c not in num_df.columns:
            converted = pd.to_numeric(df[c].astype(str).str.replace(r"[$,€£¥]", "", regex=True), errors="coerce")
            if converted.notnull().mean() > 0.6:
                num_df[c] = converted

    if num_df.empty:
        return {
            "dataset_id": dataset_id,
            "tool": "detect_outliers",
            "status": "skipped",
            "method": method,
            "message": "No numeric columns available for outlier detection.",
            "total_outlier_rows": 0,
            "column_outliers": {}
        }

    method = method.lower()
    total_rows = len(df)
    column_outliers = {}
    anomalous_indices = set()

    if method == "iqr":
        for col in num_df.columns:
            series = num_df[col].dropna()
            if len(series) < 4:
                continue
                
            q25 = float(series.quantile(0.25))
            q75 = float(series.quantile(0.75))
            iqr = q75 - q25
            lower_bound = round(q25 - (threshold * iqr), 4)
            upper_bound = round(q75 + (threshold * iqr), 4)
            
            mask = (num_df[col] < lower_bound) | (num_df[col] > upper_bound)
            outlier_idx = num_df.index[mask].tolist()
            anomalous_indices.update(outlier_idx)
            
            outlier_vals = [float(v) for v in num_df.loc[outlier_idx, col].head(10).tolist()]
            
            column_outliers[col] = {
                "outlier_count": len(outlier_idx),
                "outlier_percentage": round((len(outlier_idx) / total_rows) * 100, 2),
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "q25": round(q25, 4),
                "q75": round(q75, 4),
                "sample_outlier_values": outlier_vals,
                "outlier_indices": outlier_idx[:20]
            }

    elif method in ("zscore", "z-score"):
        z_threshold = float(threshold) if threshold != 1.5 else 2.0
        for col in num_df.columns:
            series = num_df[col].dropna()
            if len(series) < 4:
                continue
                
            mean = float(series.mean())
            std = float(series.std())
            if std == 0:
                continue
                
            z_scores = (num_df[col] - mean) / std
            mask = z_scores.abs() > z_threshold
            outlier_idx = num_df.index[mask].tolist()
            anomalous_indices.update(outlier_idx)
            
            column_outliers[col] = {
                "outlier_count": len(outlier_idx),
                "outlier_percentage": round((len(outlier_idx) / total_rows) * 100, 2),
                "mean": round(mean, 4),
                "std": round(std, 4),
                "z_threshold": z_threshold,
                "sample_outlier_values": [float(v) for v in num_df.loc[outlier_idx, col].head(10).tolist()],
                "outlier_indices": outlier_idx[:20]
            }

    elif method in ("isolation_forest", "isolationforest"):
        from sklearn.ensemble import IsolationForest
        clean_subset = num_df.dropna()
        if len(clean_subset) >= 10:
            iso = IsolationForest(contamination=0.05, random_state=42)
            preds = iso.fit_predict(clean_subset)
            outlier_idx = clean_subset.index[preds == -1].tolist()
            anomalous_indices.update(outlier_idx)
            
            column_outliers["multivariate_isolation_forest"] = {
                "outlier_count": len(outlier_idx),
                "outlier_percentage": round((len(outlier_idx) / total_rows) * 100, 2),
                "features_used": list(num_df.columns),
                "outlier_indices": outlier_idx[:20]
            }
    else:
        raise ValueError(f"Unsupported outlier detection method '{method}'. Use 'iqr', 'zscore', or 'isolation_forest'.")

    # Find columns with the most severe outliers
    ranked_cols = sorted(
        [(k, v["outlier_count"], v["outlier_percentage"]) for k, v in column_outliers.items()],
        key=lambda x: x[1],
        reverse=True
    )

    return {
        "dataset_id": dataset_id,
        "tool": "detect_outliers",
        "status": "success",
        "method": method,
        "total_rows_examined": total_rows,
        "total_anomalous_rows": len(anomalous_indices),
        "overall_anomaly_rate_percent": round((len(anomalous_indices) / total_rows) * 100, 2) if total_rows > 0 else 0.0,
        "columns_with_outliers_count": sum(1 for v in column_outliers.values() if v["outlier_count"] > 0),
        "column_outliers": column_outliers,
        "top_outlier_columns": [{"column": r[0], "count": r[1], "percentage": r[2]} for r in ranked_cols if r[1] > 0]
    }
