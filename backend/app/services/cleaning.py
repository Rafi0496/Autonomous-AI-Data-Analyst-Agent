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
from backend.app.core.config import settings
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

    @staticmethod
    def _canonical_categorical_casing(series: pd.Series) -> pd.Series:
        """
        Normalize casing/whitespace for categorical strings using canonical-form selection:
        1. Strip and collapse whitespace. Group values case-insensitively.
        2. Canonical label = most frequent original spelling in the group.
        3. On tie: prefer the variant that contains uppercase letters beyond index 0 (keeps acronyms/brands like 'HR', 'LinkedIn', 'Google Ads').
        4. If still tied: prefer the variant that starts with uppercase, then alphabetical.
        """
        from collections import Counter
        non_null_mask = series.notnull()
        if not non_null_mask.any():
            return series

        def _clean_str(val: any) -> Optional[str]:
            if val is None or pd.isna(val):
                return None
            s = str(val).strip()
            return re.sub(r"\s+", " ", s)

        cleaned_series = series.apply(_clean_str)
        non_null_vals = cleaned_series.dropna()
        if non_null_vals.empty:
            return series

        group_counts: Dict[str, Counter] = {}
        for orig in non_null_vals:
            key = orig.lower()
            if key not in group_counts:
                group_counts[key] = Counter()
            group_counts[key][orig] += 1

        def _has_upper_beyond_first(s: str) -> bool:
            return any(c.isupper() for c in s[1:])

        canonical_map: Dict[str, str] = {}
        for key, counts in group_counts.items():
            sorted_candidates = sorted(
                counts.keys(),
                key=lambda orig: (
                    -counts[orig],
                    -1 if _has_upper_beyond_first(orig) else 0,
                    -1 if (len(orig) > 0 and orig[0].isupper()) else 0,
                    orig
                )
            )
            winner = sorted_candidates[0]

            # 1. Short all-caps tokens (e.g. HR, IT)
            if winner.isupper() and len(winner) <= 4:
                canonical_map[key] = winner
            # 2. Uppercase beyond first char (e.g. LinkedIn, Google Ads)
            elif _has_upper_beyond_first(winner):
                canonical_map[key] = winner
            # 3. If winner is all lowercase, but a Title Case variant exists in the group, use Title Case
            elif winner.islower():
                title_candidates = [
                    c for c in counts.keys()
                    if c == key.title() or (len(c) > 0 and c[0].isupper() and not any(ch.isupper() for ch in c[1:]))
                ]
                if title_candidates:
                    title_winner = sorted(title_candidates, key=lambda c: -counts[c])[0]
                    canonical_map[key] = title_winner
                else:
                    canonical_map[key] = winner
            else:
                canonical_map[key] = winner

        def _map_to_canonical(val: any) -> any:
            if val is None or pd.isna(val):
                return val
            s = _clean_str(val)
            if s is None:
                return val
            return canonical_map.get(s.lower(), s)

        return series.apply(_map_to_canonical)

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

        # Scale handling: Enforce maximum row count limit (Plan §8.7)
        if original_row_count > settings.MAX_ROW_COUNT_LIMIT:
            raise ValueError(
                f"Dataset exceeds maximum supported row count for v1 ({settings.MAX_ROW_COUNT_LIMIT:,} rows). "
                f"Provided dataset has {original_row_count:,} rows. Please filter or aggregate prior to analysis."
            )

        cleaned_df = df.copy()

        # Scale handling: Representative sampling for large datasets (Plan §8.7)
        is_sampled = False
        sampling_rate = 1.0
        if original_row_count > settings.SAMPLE_THRESHOLD_ROWS:
            is_sampled = True
            sample_size = min(settings.SAMPLE_SIZE_ROWS, original_row_count)
            cleaned_df = cleaned_df.sample(n=sample_size, random_state=42).reset_index(drop=True)
            sampling_rate = round(sample_size / original_row_count, 4)
            logs.append(CleaningStepLog(
                step="scale_sampling",
                description=(
                    f"Dataset exceeds scale threshold ({settings.SAMPLE_THRESHOLD_ROWS:,} rows). "
                    f"Extracted a representative random sample of {sample_size:,} rows ({sampling_rate*100:.1f}% sampling rate) "
                    f"for exploratory analysis."
                ),
                rows_affected=original_row_count - sample_size
            ))

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

        # Step 2b: Normalize casing/whitespace for categorical columns via canonical-form selection
        str_cols_for_case = [
            c for c in cleaned_df.columns
            if (cleaned_df[c].dtype == "object"
                or str(cleaned_df[c].dtype).startswith("str")
                or str(cleaned_df[c].dtype).startswith("string"))
        ]
        normalized_case_cols: List[str] = []
        row_count_for_ratio = max(1, len(cleaned_df))
        for col in str_cols_for_case:
            unique_count = cleaned_df[col].nunique(dropna=True)
            cardinality_ratio = unique_count / row_count_for_ratio
            vals = cleaned_df[col].dropna().unique()
            lower_vals = [str(v).strip().lower() for v in vals if isinstance(v, str)]
            has_case_variance = len(lower_vals) > len(set(lower_vals))
            is_categorical = (cardinality_ratio < 0.85 or unique_count <= 250) and unique_count >= 1

            if is_categorical or has_case_variance:
                before_series = cleaned_df[col].copy()
                cleaned_df[col] = cls._canonical_categorical_casing(cleaned_df[col])
                if not before_series.equals(cleaned_df[col]):
                    normalized_case_cols.append(col)
        if normalized_case_cols:
            logs.append(CleaningStepLog(
                step="normalize_categorical_casing",
                description=(
                    "Normalized casing/whitespace in categorical columns to canonical form "
                    "(most frequent spelling; tie-break prefers uppercase beyond index 0 for acronyms/brands), "
                    "collapsing duplicates that differ only by capitalization or spacing."
                ),
                affected_columns=normalized_case_cols
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

        # Step 6a: Domain Validity Rules (convert clearly invalid values to NaN before imputation)
        invalid_values_detected: List[Dict[str, Any]] = []
        suspected_returns: List[Dict[str, Any]] = []
        non_negative_keywords = ["salary", "price", "spend", "revenue", "amount"]
        quantity_keywords = ["quantity", "count"]
        
        for col in cleaned_df.select_dtypes(include=[np.number]).columns:
            col_lower = col.lower()
            
            # Rule 1a: Negative values in quantity/count-named columns are flagged as "suspected_returns" and kept
            if any(kw in col_lower for kw in quantity_keywords):
                neg_mask = cleaned_df[col] < 0
                neg_count = int(neg_mask.sum())
                if neg_count > 0:
                    suspected_returns.append({
                        "column": col,
                        "count": neg_count,
                        "description": f"Suspected returns: {neg_count} negative values in '{col}' kept."
                    })
                    logs.append(CleaningStepLog(
                        step="flag_suspected_returns",
                        description=f"Flagged {neg_count} negative values in '{col}' as suspected returns (kept in dataset).",
                        affected_columns=[col],
                        rows_affected=neg_count
                    ))
            # Rule 1b: Invalidate negatives in salary/price/spend/revenue/amount columns
            elif any(kw in col_lower for kw in non_negative_keywords):
                neg_mask = cleaned_df[col] < 0
                neg_count = int(neg_mask.sum())
                if neg_count > 0:
                    cleaned_df.loc[neg_mask, col] = np.nan
                    invalid_values_detected.append({
                        "column": col,
                        "rule": "non_negative_constraint",
                        "count": neg_count,
                        "description": f"Negative value in non-negative column '{col}'"
                    })
                    logs.append(CleaningStepLog(
                        step="domain_validity_rules",
                        description=f"Replaced {neg_count} negative values in non-negative column '{col}' with NaN prior to imputation.",
                        affected_columns=[col],
                        rows_affected=neg_count
                    ))
            
            # Rule 2: Age bounds [0, 100]
            is_age_col = (col_lower == "age") or ("age" in col_lower.split("_"))
            if is_age_col:
                age_mask = (cleaned_df[col] < 0) | (cleaned_df[col] > 100)
                age_count = int(age_mask.sum())
                if age_count > 0:
                    cleaned_df.loc[age_mask, col] = np.nan
                    invalid_values_detected.append({
                        "column": col,
                        "rule": "age_bounds_0_100",
                        "count": age_count,
                        "description": f"Age value out of valid bounds [0, 100] in '{col}'"
                    })
                    logs.append(CleaningStepLog(
                        step="domain_validity_rules",
                        description=f"Replaced {age_count} invalid age values (< 0 or > 100) in '{col}' with NaN prior to imputation.",
                        affected_columns=[col],
                        rows_affected=age_count
                    ))

        # Step 6b: Sentinel rule: auto-convert to NaN only for known placeholder patterns
        # (999, 9999, 99999, -1, -999, -9999) repeated >= 3 times and outside the 3x IQR fence.
        # Other repeated extreme values go into the cleaning report as "suspected_repeated_extremes" and are NOT deleted.
        sentinels_detected: List[Dict[str, Any]] = []
        suspected_repeated_extremes: List[Dict[str, Any]] = []
        KNOWN_SENTINEL_PATTERNS = {999, 9999, 99999, -1, -999, -9999, 999.0, 9999.0, 99999.0, -1.0, -999.0, -9999.0}

        num_cols_for_sentinels = cleaned_df.select_dtypes(include=[np.number]).columns.tolist()
        for col in num_cols_for_sentinels:
            series = cleaned_df[col].dropna()
            if len(series) < 6:
                continue

            val_counts = series.value_counts()
            candidates = val_counts[val_counts >= 3].index.tolist()

            for cand in candidates:
                cand_val = float(cand)
                subset = series[series != cand]
                if len(subset) < 5:
                    continue

                q1 = float(subset.quantile(0.25))
                q3 = float(subset.quantile(0.75))
                iqr = q3 - q1
                if iqr <= 0:
                    continue

                lower_fence = q1 - 3.0 * iqr
                upper_fence = q3 + 3.0 * iqr

                if cand_val < lower_fence or cand_val > upper_fence:
                    count = int(val_counts[cand])
                    if cand in KNOWN_SENTINEL_PATTERNS or cand_val in KNOWN_SENTINEL_PATTERNS:
                        cleaned_df.loc[cleaned_df[col] == cand, col] = np.nan
                        sentinels_detected.append({
                            "column": col,
                            "sentinel_value": cand_val if cand_val.is_integer() else cand_val,
                            "count": count
                        })
                        logs.append(CleaningStepLog(
                            step="replace_sentinel_values",
                            description=(
                                f"Replaced {count} occurrences of known placeholder sentinel value {cand} in column '{col}' "
                                f"with NaN prior to imputation (outside 3x IQR fence [{lower_fence:.2f}, {upper_fence:.2f}])."
                            ),
                            affected_columns=[col],
                            rows_affected=count
                        ))
                    else:
                        suspected_repeated_extremes.append({
                            "column": col,
                            "value": cand_val if cand_val.is_integer() else cand_val,
                            "count": count,
                            "lower_fence": round(lower_fence, 2),
                            "upper_fence": round(upper_fence, 2),
                            "description": f"Repeated extreme value {cand} ({count} occurrences) in '{col}' outside 3x IQR fence [{lower_fence:.2f}, {upper_fence:.2f}] kept."
                        })
                        logs.append(CleaningStepLog(
                            step="flag_suspected_repeated_extremes",
                            description=(
                                f"Flagged {count} occurrences of extreme value {cand} in column '{col}' as suspected repeated extreme (kept in dataset)."
                            ),
                            affected_columns=[col],
                            rows_affected=count
                        ))

        # Step 7: Missing Value Imputation & Transparency Tracking
        missing_imputed: Dict[str, int] = {}
        column_imputation_stats: Dict[str, Dict[str, Any]] = {}
        imputed_mask = pd.DataFrame(False, index=cleaned_df.index, columns=cleaned_df.columns)

        num_cols = cleaned_df.select_dtypes(include=[np.number]).columns
        for col in num_cols:
            null_series = cleaned_df[col].isnull()
            null_count = int(null_series.sum())
            if null_count > 0:
                imputed_mask[col] = null_series
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
                column_imputation_stats[col] = {
                    "missing_count": null_count,
                    "imputed_count": null_count,
                    "imputation_rate": round(null_count / max(1, len(cleaned_df)), 4),
                    "strategy": str(strategy),
                    "fill_value": round(fill_val, 4)
                }
                logs.append(CleaningStepLog(
                    step="impute_numeric_nulls",
                    description=f"Imputed {null_count} nulls in numeric column '{col}' with value {fill_val:.2f}.",
                    affected_columns=[col],
                    rows_affected=null_count
                ))
            else:
                column_imputation_stats[col] = {
                    "missing_count": 0,
                    "imputed_count": 0,
                    "imputation_rate": 0.0
                }

        cat_cols = [c for c in cleaned_df.columns if c not in num_cols and not pd.api.types.is_datetime64_any_dtype(cleaned_df[c])]
        for col in cat_cols:
            null_series = cleaned_df[col].isnull()
            null_count = int(null_series.sum())
            if null_count > 0:
                imputed_mask[col] = null_series
                strategy = options.missing_cat_strategy
                if strategy in (MissingValueStrategy.AUTO, MissingValueStrategy.MODE):
                    mode_val = cleaned_df[col].mode(dropna=True)
                    fill_val = mode_val.iloc[0] if not mode_val.empty else "Unknown"
                else:
                    fill_val = "Unknown"

                cleaned_df[col] = cleaned_df[col].fillna(fill_val)
                missing_imputed[col] = null_count
                column_imputation_stats[col] = {
                    "missing_count": null_count,
                    "imputed_count": null_count,
                    "imputation_rate": round(null_count / max(1, len(cleaned_df)), 4),
                    "strategy": str(strategy),
                    "fill_value": str(fill_val)
                }
                logs.append(CleaningStepLog(
                    step="impute_categorical_nulls",
                    description=f"Imputed {null_count} nulls in categorical column '{col}' with '{fill_val}'.",
                    affected_columns=[col],
                    rows_affected=null_count
                ))
            else:
                column_imputation_stats[col] = {
                    "missing_count": 0,
                    "imputed_count": 0,
                    "imputation_rate": 0.0
                }

        # Attach mask to cleaned_df
        cleaned_df.attrs["imputed_mask"] = imputed_mask

        # Save cleaned file and companion mask if output path provided
        saved_path_str = ""
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cleaned_df.to_csv(output_path, index=False)
            mask_path = output_path.with_name(f"{output_path.stem}_imputed_mask.csv")
            imputed_mask.to_csv(mask_path, index=False)
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
            column_imputation_stats=column_imputation_stats,
            sentinels_detected=sentinels_detected,
            invalid_values_detected=invalid_values_detected,
            suspected_repeated_extremes=suspected_repeated_extremes,
            suspected_returns=suspected_returns,
            duplicates_removed=duplicates_removed,
            is_sampled=is_sampled,
            sampling_rate=sampling_rate,
            population_row_count=original_row_count,
            logs=logs,
            cleaned_file_path=saved_path_str
        )

        cleaned_df.attrs["cleaning_report"] = result.model_dump()
        if output_path:
            try:
                import json
                report_path = output_path.with_name(f"{output_path.stem}_cleaning_report.json")
                with open(report_path, "w", encoding="utf-8") as f:
                    json.dump(result.model_dump(), f, default=str, indent=2)
            except Exception:
                pass

        return cleaned_df, result

clean_data = DataCleaningService.clean_data
