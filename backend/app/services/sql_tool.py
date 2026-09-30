"""DuckDB-powered ad-hoc SQL querying tool: query_sql().

Provides safe, sandboxed, read-only analytical SQL execution strictly scoped to the dataset.
Rejects any writes, external filesystem access, pragma changes, or query chaining.
"""
import re
import time
from typing import Any, Dict, List
import duckdb
import pandas as pd
from backend.app.services.data_loader import get_dataset_dataframe

FORBIDDEN_SQL_KEYWORDS = [
    r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b", r"\bALTER\b",
    r"\bCREATE\b", r"\bATTACH\b", r"\bDETACH\b", r"\bCOPY\b", r"\bEXPORT\b",
    r"\bIMPORT\b", r"\bPRAGMA\b", r"\bINSTALL\b", r"\bLOAD\b", r"\bSET\b",
    r"\bCALL\b", r"\bEXEC\b", r"\bEXECUTE\b", r"\bGRANT\b", r"\bREVOKE\b"
]

FORBIDDEN_PATH_PATTERNS = [
    r"\.\.[/\\]", r"/[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+", r"[a-zA-Z]:[/\\]",
    r"read_csv", r"read_parquet", r"read_json", r"scan_csv", r"scan_parquet",
    r"http[s]?://"
]

def query_sql(dataset_id: str, sql: str, max_rows: int = 200) -> Dict[str, Any]:
    """
    Execute a read-only SQL query over the dataset via an in-memory DuckDB connection.
    The dataset is queryable via the table name 'df' or 'dataset'.
    """
    clean_query = sql.strip()

    # 1. Reject empty queries
    if not clean_query:
        raise ValueError("SQL query cannot be empty.")

    # 2. Reject semicolon-chained multi-statements
    trimmed = clean_query.rstrip(";")
    if ";" in trimmed:
        raise ValueError("Multi-statement SQL queries are prohibited for security.")

    # 3. Reject modification keywords
    for pattern in FORBIDDEN_SQL_KEYWORDS:
        if re.search(pattern, clean_query, re.IGNORECASE):
            raise ValueError(f"Forbidden SQL keyword detected. Only read-only SELECT queries are permitted.")

    # 4. Reject external filesystem access or scanner functions
    for pattern in FORBIDDEN_PATH_PATTERNS:
        if re.search(pattern, clean_query, re.IGNORECASE):
            raise ValueError(f"External filesystem access or scanner functions are prohibited.")

    # 5. Query must begin with SELECT or WITH
    if not re.match(r"^(SELECT|WITH)\b", clean_query, re.IGNORECASE):
        raise ValueError("Query must begin with SELECT or WITH.")

    # Load cleaned dataset and prepare observed view (imputed cells set to NULL)
    clean_df = get_dataset_dataframe(dataset_id, prefer_cleaned=True)
    from backend.app.services.data_loader import get_column_imputed_mask
    observed_df = clean_df.copy()
    for col in clean_df.columns:
        mask = get_column_imputed_mask(clean_df, col)
        if mask.any():
            observed_df.loc[mask, col] = None

    # Execute in an isolated in-memory DuckDB instance
    start_time = time.perf_counter()
    con = duckdb.connect(database=":memory:", read_only=False)
    try:
        # Register dataframe strictly under local aliases
        # 'data_clean': all cleaned rows (sentinels and invalid values sanitized/imputed)
        # 'data_observed': only observed non-imputed rows (imputed cells are NULL)
        # 'df' and 'dataset': aliases pointing to data_clean for backward compatibility
        con.register("data_clean", clean_df)
        con.register("data_observed", observed_df)
        con.register("df", clean_df)
        con.register("dataset", clean_df)

        # Enforce limit if missing
        if not re.search(r"\bLIMIT\s+\d+", clean_query, re.IGNORECASE):
            clean_query = f"{clean_query} LIMIT {max_rows}"

        res_df = con.execute(clean_query).df()
        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        
        # Serialize NaNs to None for JSON
        rows = res_df.replace({float('nan'): None}).to_dict(orient="records")

        return {
            "dataset_id": dataset_id,
            "tool": "query_sql",
            "status": "success",
            "query": sql,
            "execution_time_ms": execution_time_ms,
            "row_count": len(rows),
            "columns": list(res_df.columns),
            "rows": rows
        }
    except Exception as e:
        raise ValueError(f"DuckDB execution error: {str(e)}")
    finally:
        con.close()
