"""Data cleaning pipeline: clean_data() standalone testable service.

Handles:
- Missing value imputation (auto / mean / median / mode / constant)
- Duplicate row detection & removal
- Type inference & coercion (strings with currency/commas to numbers, dates)
- Column trimming & normalization
- Constant column & excessive null column removal
- Complete audit logging of all transformations
"""
import re
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from shared.constants import MissingValueStrategy
from shared.schemas.dataset import CleaningStepLog, DatasetCleaningOptions, DatasetCleaningResult

class DataCleaningService:
    @staticmethod
    def _clean_currency_string(val: any) -> any:
        if val is None or pd.isna(val):
            return np.nan
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            cleaned = re.sub(r"[$,€£¥]", "", val.strip())
            cleaned = cleaned.replace(",", "")
            try:
                return float(cleaned)
            except ValueError:
                return val
        return val

    @classmethod
    def clean_data(
        cls,
        df: pd.DataFrame,
        dataset_id: str,
        output_path: Optional[Path] = None,
        options: Optional[DatasetCleaningOptions] = None
    ) -> Tuple[pd.DataFrame, DatasetCleaningResult]:
        """Execute comprehensive deterministic data cleaning on a pandas DataFrame."""
        if options is None:
            options = DatasetCleaningOptions()
            
        logs: List[CleaningStepLog] = []
        original_row_count, original_col_count = df.shape
        cleaned_df = df.copy()

        # Step 1: Strip whitespace from column headers
        cleaned_df.columns = [str(c).strip() for c in cleaned_df.columns]
        logs.append(CleaningStepLog(
            step="normalize_headers",
            description="Stripped leading and trailing whitespace from column headers.",
            affected_columns=list(cleaned_df.columns)
        ))

        # Step 2: Strip whitespace from string cells
        if options.strip_whitespace:
            str_cols = [c for c in cleaned_df.columns if cleaned_df[c].dtype == "object" or str(cleaned_df[c].dtype).startswith("str") or str(cleaned_df[c].dtype).startswith("string")]
            for col in str_cols:
                cleaned_df[col] = cleaned_df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
            logs.append(CleaningStepLog(
                step="strip_string_whitespace",
                description="Trimmed leading and trailing whitespace across text columns.",
                affected_columns=str_cols
            ))

        # Step 3: Remove duplicate rows
        duplicates_removed = 0
        if options.drop_duplicates:
            duplicates_removed = int(cleaned_df.duplicated().sum())
            if duplicates_removed > 0:
                cleaned_df = cleaned_df.drop_duplicates().reset_index(drop=True)
                logs.append(CleaningStepLog(
                    step="remove_duplicates",
                    description=f"Removed {duplicates_removed} duplicate rows.",
                    rows_affected=duplicates_removed
                ))

        # Step 4: Drop columns with excessive missing values
        dropped_cols: List[str] = []
        missing_fractions = cleaned_df.isnull().mean()
        for col, frac in missing_fractions.items():
            if frac >= options.missing_threshold_drop_col and len(cleaned_df.columns) > 1:
                dropped_cols.append(col)
        if dropped_cols:
            cleaned_df = cleaned_df.drop(columns=dropped_cols)
            logs.append(CleaningStepLog(
                step="drop_excessive_null_columns",
                description=f"Dropped columns with >= {options.missing_threshold_drop_col * 100:.0f}% null values.",
                affected_columns=dropped_cols
            ))

        # Step 5: Drop constant columns
        if options.remove_constant_columns:
            constant_cols = [c for c in cleaned_df.columns if cleaned_df[c].nunique(dropna=False) <= 1]
            if constant_cols and len(cleaned_df.columns) > len(constant_cols):
                cleaned_df = cleaned_df.drop(columns=constant_cols)
                dropped_cols.extend(constant_cols)
                logs.append(CleaningStepLog(
                    step="drop_constant_columns",
                    description="Dropped single-value constant columns.",
                    affected_columns=constant_cols
                ))

        # Step 6: Type Coercion (Currency / numbers formatted as strings & Dates)
        type_conversions: Dict[str, str] = {}
        candidate_cols = [c for c in cleaned_df.columns if not pd.api.types.is_numeric_dtype(cleaned_df[c]) and not pd.api.types.is_datetime64_any_dtype(cleaned_df[c])]
        
        for col in candidate_cols:
            non_null = cleaned_df[col].dropna()
            if non_null.empty:
                continue

            # A: Try currency / numeric coercion
            cleaned_series = non_null.apply(cls._clean_currency_string)
            numeric_test = pd.to_numeric(cleaned_series, errors="coerce")
            valid_num_fraction = numeric_test.notnull().mean()

            if valid_num_fraction >= 0.60:
                # Successfully coercible to numeric
                cleaned_df[col] = pd.to_numeric(cleaned_df[col].apply(cls._clean_currency_string), errors="coerce")
                type_conversions[col] = "numeric"
                logs.append(CleaningStepLog(
                    step="coerce_to_numeric",
                    description=f"Converted currency/formatted strings in column '{col}' to numeric float.",
                    affected_columns=[col]
                ))
                continue

            # B: Try date coercion
            if options.coerce_dates:
                is_date_named = any(k in col.lower() for k in ["date", "time", "year", "month", "day", "dob", "period"])
                if is_date_named or non_null.astype(str).str.contains(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}", regex=True).mean() > 0.5:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        date_test = pd.to_datetime(non_null, errors="coerce")
                    if date_test.notnull().mean() >= 0.60:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            cleaned_df[col] = pd.to_datetime(cleaned_df[col], errors="coerce")
                        type_conversions[col] = "datetime"
                        logs.append(CleaningStepLog(
                            step="coerce_datetime",
                            description=f"Coerced mixed date formats in column '{col}' to datetime.",
                            affected_columns=[col]
                        ))
                        continue

        # Step 7: Missing Value Imputation
        missing_imputed: Dict[str, int] = {}
        num_cols = cleaned_df.select_dtypes(include=[np.number]).columns
        for col in num_cols:
            null_count = int(cleaned_df[col].isnull().sum())
            if null_count > 0:
                strategy = options.missing_num_strategy
                valid_vals = cleaned_df[col].dropna()
                if valid_vals.empty:
                    fill_val = 0.0
                elif strategy == MissingValueStrategy.AUTO:
                    skewness = valid_vals.skew() if len(valid_vals) > 2 else 0
                    fill_val = float(valid_vals.median()) if abs(skewness) > 1.0 else float(valid_vals.mean())
                elif strategy == MissingValueStrategy.MEDIAN:
                    fill_val = float(valid_vals.median())
                elif strategy == MissingValueStrategy.MEAN:
                    fill_val = float(valid_vals.mean())
                elif strategy == MissingValueStrategy.CONSTANT:
                    fill_val = 0.0
                else:
                    fill_val = float(valid_vals.median())

                cleaned_df[col] = cleaned_df[col].fillna(fill_val)
                missing_imputed[col] = null_count
                logs.append(CleaningStepLog(
                    step="impute_numeric_nulls",
                    description=f"Imputed {null_count} nulls in numeric column '{col}' with value {fill_val:.2f}.",
                    affected_columns=[col],
                    rows_affected=null_count
                ))

        cat_cols = [c for c in cleaned_df.columns if c not in num_cols and not pd.api.types.is_datetime64_any_dtype(cleaned_df[c])]
        for col in cat_cols:
            null_count = int(cleaned_df[col].isnull().sum())
            if null_count > 0:
                strategy = options.missing_cat_strategy
                if strategy in (MissingValueStrategy.AUTO, MissingValueStrategy.MODE):
                    mode_val = cleaned_df[col].mode(dropna=True)
                    fill_val = mode_val.iloc[0] if not mode_val.empty else "Unknown"
                else:
                    fill_val = "Unknown"

                cleaned_df[col] = cleaned_df[col].fillna(fill_val)
                missing_imputed[col] = null_count
                logs.append(CleaningStepLog(
                    step="impute_categorical_nulls",
                    description=f"Imputed {null_count} nulls in categorical column '{col}' with '{fill_val}'.",
                    affected_columns=[col],
                    rows_affected=null_count
                ))

        # Save cleaned file if output path provided
        saved_path_str = ""
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cleaned_df.to_csv(output_path, index=False)
            saved_path_str = str(output_path)

        result = DatasetCleaningResult(
            dataset_id=dataset_id,
            original_row_count=original_row_count,
            cleaned_row_count=len(cleaned_df),
            original_col_count=original_col_count,
            cleaned_col_count=len(cleaned_df.columns),
            dropped_columns=dropped_cols,
            type_conversions=type_conversions,
            missing_values_imputed=missing_imputed,
            duplicates_removed=duplicates_removed,
            logs=logs,
            cleaned_file_path=saved_path_str
        )

        return cleaned_df, result

clean_data = DataCleaningService.clean_data
