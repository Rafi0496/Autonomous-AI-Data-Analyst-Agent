"""Correlation analysis tool: run_correlation().

Computes pairwise correlations across numeric columns and flags notable relationships.
"""
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from backend.app.services.data_loader import get_dataset_dataframe

def run_correlation(
    dataset_id: str,
    columns: Optional[List[str]] = None,
    threshold: float = 0.4
) -> Dict[str, Any]:
    """
    Compute pairwise correlation across numeric columns in the dataset.
    Flags strong linear relationships (|r| >= threshold).
    """
    df = get_dataset_dataframe(dataset_id, prefer_cleaned=True)
    from backend.app.services.data_loader import get_column_imputed_mask
    
    # Filter to requested columns or all numeric columns
    if columns:
        valid_cols = [c for c in columns if c in df.columns]
    else:
        valid_cols = df.columns.tolist()
        
    num_df = df[valid_cols].select_dtypes(include=[np.number]).copy()
    
    # Try converting numeric-like object columns if too few numeric cols
    if len(num_df.columns) < 2:
        for c in valid_cols:
            if c not in num_df.columns:
                converted = pd.to_numeric(df[c].astype(str).str.replace(r"[$,€£¥]", "", regex=True), errors="coerce")
                if converted.notnull().mean() > 0.6:
                    num_df[c] = converted

    if len(num_df.columns) < 2:
        return {
            "dataset_id": dataset_id,
            "status": "skipped",
            "message": "Fewer than 2 numeric columns found to calculate correlation.",
            "columns_analyzed": list(num_df.columns),
            "correlation_matrix": {},
            "strong_relationships": [],
            "highest_correlation": None
        }

    matrix_cols = list(num_df.columns)
    corr_dict = {c: {} for c in matrix_cols}
    strong_relationships = []
    all_pairs = []
    row_imputed = pd.Series(False, index=df.index)
    for c in matrix_cols:
        row_imputed = (row_imputed | get_column_imputed_mask(df, c))
    total_excluded_imputed = int(row_imputed.sum())
    n_used = len(df) - total_excluded_imputed

    for i in range(len(matrix_cols)):
        col_x = matrix_cols[i]
        corr_dict[col_x][col_x] = 1.0
        x_imputed = get_column_imputed_mask(df, col_x)

        for j in range(i + 1, len(matrix_cols)):
            col_y = matrix_cols[j]
            y_imputed = get_column_imputed_mask(df, col_y)
            pair_imputed = (x_imputed | y_imputed)
            pair_subset = num_df.loc[~pair_imputed, [col_x, col_y]].dropna()
            
            pair_n_used = int(len(pair_subset))
            pair_n_excluded = int(pair_imputed.sum())

            if pair_n_used >= 2:
                r_val = round(float(pair_subset[col_x].corr(pair_subset[col_y])), 4)
            else:
                r_val = float("nan")

            corr_dict[col_x][col_y] = None if np.isnan(r_val) else r_val
            if col_y not in corr_dict:
                corr_dict[col_y] = {}
            corr_dict[col_y][col_x] = None if np.isnan(r_val) else r_val

            if pd.isna(r_val) or np.isnan(r_val):
                continue

            abs_r = abs(r_val)
            strength_desc = "weak"
            if abs_r >= 0.7:
                strength_desc = "very strong"
            elif abs_r >= 0.5:
                strength_desc = "strong"
            elif abs_r >= 0.3:
                strength_desc = "moderate"
                
            direction = "positive" if r_val > 0 else "negative"
            
            rel_info = {
                "column_x": col_x,
                "column_y": col_y,
                "correlation": float(r_val),
                "abs_correlation": float(abs_r),
                "strength": f"{strength_desc} {direction}",
                "sample_size": pair_n_used,
                "n_used": pair_n_used,
                "n_excluded_imputed": pair_n_excluded
            }
            
            all_pairs.append(rel_info)
            if abs_r >= threshold:
                strong_relationships.append(rel_info)

    all_pairs.sort(key=lambda x: x["abs_correlation"], reverse=True)
    strong_relationships.sort(key=lambda x: x["abs_correlation"], reverse=True)
    highest = all_pairs[0] if all_pairs else None

    return {
        "dataset_id": dataset_id,
        "tool": "run_correlation",
        "status": "success",
        "columns_analyzed": matrix_cols,
        "total_pairs_computed": int(len(matrix_cols) * (len(matrix_cols) - 1) / 2),
        "strong_relationships_count": len(strong_relationships),
        "strong_relationships": strong_relationships,
        "highest_correlation": highest,
        "correlation_matrix": corr_dict,
        "total_records": len(df),
        "n_used": n_used,
        "n_excluded_imputed": total_excluded_imputed
    }
