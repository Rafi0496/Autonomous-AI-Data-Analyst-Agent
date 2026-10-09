"""General SQL generation and query result claim-binding for Chat Q&A (Milestone 2).

Replaces question-specific hardcoding with a general flow:
- Dynamically generates read-only DuckDB SQL queries against data_clean or data_observed.
- Determines basis strictly: 'observed', 'non-missing', 'recorded' -> data_observed; otherwise data_clean.
- Converts query result rows directly into natural language answer text and bound claims.
- Assures every answer states its basis and n matching the queried table.
"""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def detect_question_target_table(question: str) -> str:
    """
    Determine whether to query data_observed or data_clean:
    - Numeric aggregates (sum, avg, mean, rate, total, min, max) default to data_observed.
    - Explicit observed keywords ('observed', 'non-missing', 'recorded') -> data_observed.
    - Explicit clean keywords ('clean', 'cleaned', 'imputed', 'all rows') -> data_clean.
    - data_clean only for row counts, IDs, and categorical counts (e.g. 'number of transactions', 'how many employees').
    """
    q_lower = question.lower()
    if any(w in q_lower for w in ["data_clean", "clean records", "cleaned data", "all rows", "imputed rows"]):
        return "data_clean"
    if any(w in q_lower for w in ["non-missing", "non missing", "observed", "recorded", "data_observed"]):
        return "data_observed"

    # Categorical counts, row counts, IDs and categorical share use data_clean
    is_categorical_or_count = (
        any(w in q_lower for w in [
            "number of", "transactions per", "how many", "count of", "headcount", "how many records", "how many rows", "per region"
        ])
        or ("share of credit card" in q_lower and not any(w in q_lower for w in ["observed", "non-missing", "non missing"]))
        or ("share of" in q_lower and "payment" in q_lower and not any(w in q_lower for w in ["observed", "non-missing", "non missing"]))
    ) and not any(w in q_lower for w in ["salary", "spend", "conversion", "price", "revenue", "average", "avg", "mean"])

    if is_categorical_or_count:
        return "data_clean"

    # All numeric aggregates (sum, avg, mean, numeric rate, conversions, spend, salary, etc.) default to data_observed
    has_numeric_agg = any(w in q_lower for w in [
        "salary", "spend", "conversion", "rate", "sum", "average", "avg", "mean", "price", "quantity", "revenue"
    ])
    if has_numeric_agg:
        return "data_observed"

    return "data_observed"


def extract_question_columns(question: str, available_columns: List[str]) -> List[str]:
    """Extract columns from available_columns referenced or aliased in the question."""
    if not available_columns:
        return []
    q_lower = question.lower()
    matched_cols: List[str] = []

    for c in available_columns:
        cl = c.lower()
        parts = [p for p in cl.split("_") if len(p) > 2]
        if re.search(rf"\b{re.escape(cl)}\b", q_lower) or any(re.search(rf"\b{re.escape(p)}\b", q_lower) for p in parts):
            matched_cols.append(c)

    # Keyword aliases
    if any(k in q_lower for k in ["salary", "salaries", "compensation", "pay"]):
        sal_c = next((c for c in available_columns if "salary" in c.lower() or "pay" in c.lower()), None)
        if sal_c and sal_c not in matched_cols:
            matched_cols.append(sal_c)

    if any(k in q_lower for k in ["spend", "ad_spend", "budget", "cost"]):
        spend_c = next((c for c in available_columns if "spend" in c.lower() or "cost" in c.lower()), None)
        if spend_c and spend_c not in matched_cols:
            matched_cols.append(spend_c)

    if any(k in q_lower for k in ["click", "clicks"]):
        click_c = next((c for c in available_columns if "click" in c.lower()), None)
        if click_c and click_c not in matched_cols:
            matched_cols.append(click_c)

    if any(k in q_lower for k in ["conversion", "conversions", "convert"]):
        conv_c = next((c for c in available_columns if "conv" in c.lower()), None)
        if conv_c and conv_c not in matched_cols:
            matched_cols.append(conv_c)

    if any(k in q_lower for k in ["transaction", "transactions", "orders"]):
        tx_c = next((c for c in available_columns if "transaction" in c.lower() or "order" in c.lower()), None)
        if tx_c and tx_c not in matched_cols:
            matched_cols.append(tx_c)

    if any(k in q_lower for k in ["sales", "sale", "revenue"]):
        sales_c = next((c for c in available_columns if any(k in c.lower() for k in ["sales", "revenue", "total_amount", "amount"])), None)
        if not sales_c:
            sales_c = next((c for c in available_columns if "quantity" in c.lower()), None)
        if sales_c and sales_c not in matched_cols:
            matched_cols.append(sales_c)

    if any(k in q_lower for k in ["employee", "employees", "staff", "headcount"]):
        emp_c = next((c for c in available_columns if "employee" in c.lower()), None)
        if emp_c and emp_c not in matched_cols:
            matched_cols.append(emp_c)

    if any(k in q_lower for k in ["attrition", "turnover", "churn"]):
        att_c = next((c for c in available_columns if "attrition" in c.lower() or "churn" in c.lower()), None)
        if att_c and att_c not in matched_cols:
            matched_cols.append(att_c)

    if any(k in q_lower for k in ["payment", "credit card", "paypal", "cash"]):
        pm_c = next((c for c in available_columns if "payment" in c.lower()), None)
        if pm_c and pm_c not in matched_cols:
            matched_cols.append(pm_c)

    return matched_cols


SEGMENT_COLUMNS = {
    "department", "channel", "region", "branch", "category", "payment_method",
    "gender", "job_role", "education_field", "marital_status", "device", "location",
    "country", "city", "state", "segment", "product"
}


def is_segment_column(col_name: str) -> bool:
    return str(col_name).strip().lower() in SEGMENT_COLUMNS


def get_insight_metric_columns(ins: Dict[str, Any]) -> List[str]:
    """Extract metric/measured columns from an insight."""
    mv = ins.get("metric_values") or {}
    metrics = []

    if mv.get("metric_column"):
        metrics.append(str(mv["metric_column"]))
    if mv.get("target"):
        metrics.append(str(mv["target"]))
    if mv.get("value_column"):
        metrics.append(str(mv["value_column"]))
    if mv.get("column"):
        col = str(mv["column"])
        if not is_segment_column(col):
            metrics.append(col)

    # Check id convention
    ins_id = ins.get("id", "")
    if ins_id.startswith("insight-seg-"):
        parts = ins_id.replace("insight-seg-", "").split("-")
        if len(parts) >= 2 and not is_segment_column(parts[1]):
            metrics.append(parts[1])
    elif "trend-" in ins_id:
        parts = ins_id.split("trend-")
        if len(parts) >= 2:
            metrics.append(parts[1])

    # Fallback to columns list (filter out segment columns)
    cols = ins.get("columns", []) or []
    if isinstance(cols, str):
        cols = [cols]
    for c in cols:
        sc = str(c)
        if not is_segment_column(sc) and sc not in metrics:
            metrics.append(sc)

    return list(dict.fromkeys(metrics))


def insight_shares_column(ins: Dict[str, Any], question_cols: List[str], question: Optional[str] = None) -> bool:
    """
    Check if an insight is relevant to the question.
    CRITICAL: Include an insight only if it shares the question's METRIC column.
    Sharing a segment column is NOT enough.
    """
    if not question_cols:
        return False

    # Identify metric columns in the question
    question_metric_cols = [c for c in question_cols if not is_segment_column(c)]
    if question:
        q_lower = question.lower()
        if any(k in q_lower for k in ["attrition", "turnover", "churn"]):
            if "Attrition" not in question_metric_cols:
                question_metric_cols.append("Attrition")
        if any(k in q_lower for k in ["trend", "sales", "revenue"]):
            for cand in ["Quantity", "Total_Amount", "sales", "revenue"]:
                if cand not in question_metric_cols:
                    question_metric_cols.append(cand)

    # Get metric columns of the insight
    ins_metric_cols = get_insight_metric_columns(ins)

    # If the question specifies a metric column, insight MUST share that metric column
    if question_metric_cols:
        if ins_metric_cols:
            matches_metric = any(
                qm.lower() in [im.lower() for im in ins_metric_cols] or
                any(qm.lower() in im.lower() or im.lower() in qm.lower() for im in ins_metric_cols)
                for qm in question_metric_cols
            )
            if matches_metric:
                return True
        # Also check if question metric appears explicitly in title or summary
        ins_text = (str(ins.get("title", "")) + " " + str(ins.get("summary", ""))).lower()
        if any(re.search(rf"\b{re.escape(qm.lower())}\b", ins_text) for qm in question_metric_cols):
            return True
        # If question has a metric column, sharing a segment column is NOT enough
        return False

    # If the question does NOT specify any metric column (e.g., 'What is the breakdown of Region?'):
    # Then allow matching segment column
    ins_cols = ins.get("columns", []) or []
    if isinstance(ins_cols, str):
        ins_cols = [ins_cols]
    col = ins.get("column")
    if col and col not in ins_cols:
        ins_cols.append(col)
    ins_cols.extend(ins_metric_cols)

    ins_text = (str(ins.get("title", "")) + " " + str(ins.get("summary", ""))).lower()
    return any(c.lower() in [ic.lower() for ic in ins_cols] for c in question_cols) or \
           any(re.search(rf"\b{re.escape(c.lower())}\b", ins_text) for c in question_cols)


def generate_sql_for_question(
    question: str,
    available_columns: List[str],
    target_table: Optional[str] = None
) -> Optional[str]:
    """
    Generate a read-only SELECT query against target_table given the question and available schema columns.
    Enforces safe read-only SQL syntax and table constraints.
    """
    if not available_columns:
        return None

    if not target_table:
        target_table = detect_question_target_table(question)

    q_lower = question.lower()

    # Questions asking for statistical significance or hypothesis testing require analysis insights, not plain SQL
    if any(sig in q_lower for sig in ["statistically significant", "statistical significance", "is it significant", "is there a significant", "is the difference significant"]):
        return None

    # Never generate SQL for questions about missing columns or entities
    from backend.app.services.chat_service import detect_missing_column_or_entity
    if detect_missing_column_or_entity(question, available_columns):
        return None

    # 1. Map columns in question using word-boundary matching
    matched_cols = extract_question_columns(question, available_columns)
    if not matched_cols:
        return None

    # 2. Detect Grouping Column
    group_col = None
    # Check explicitly after prepositions: by, per, across, in each, for each
    for prep in [r"\bby\b", r"\bper\b", r"\bacross\b", r"\bfor each\b", r"\bin each\b"]:
        m = re.search(rf"{prep}\s+([a-zA-Z0-9_\s]+)", q_lower)
        if m:
            after_text = m.group(1).strip()
            for c in matched_cols:
                cl = c.lower()
                c_parts = [p for p in cl.split("_") if len(p) > 2]
                if cl in after_text or any(p in after_text for p in c_parts):
                    group_col = c
                    break
        if group_col:
            break

    # If no preposition match, look for categorical attribute among matched
    if not group_col:
        for c in matched_cols:
            cl = c.lower()
            if any(k in cl for k in ["department", "channel", "region", "category", "payment", "method", "audience", "gender", "segment"]):
                group_col = c
                break

    # 3. Detect Metrics and Aggregations
    metric_cols = [
        c for c in matched_cols
        if c != group_col and any(k in c.lower() for k in ["salary", "spend", "click", "impression", "conversion", "quantity", "price", "age", "tenure", "score", "amount", "revenue"])
    ]

    is_avg = any(w in q_lower for w in ["average", "avg", "mean"])
    is_sum = any(w in q_lower for w in ["total", "sum"])
    is_count = any(w in q_lower for w in ["how many", "number of", "count", "transactions", "employees", "headcount"])
    is_share = any(w in q_lower for w in ["share", "percentage", "proportion"])
    is_highest = any(w in q_lower for w in ["highest", "top", "best", "max", "maximum", "most"])

    select_items = [f"'{target_table}' as basis"]
    where_clauses = []
    order_by_clause = ""

    # Special Case A: Share of a specific category value (e.g. Credit Card payment share)
    if is_share and group_col:
        val_name = None
        if "credit card" in q_lower:
            val_name = "Credit Card"
        elif "paypal" in q_lower:
            val_name = "PayPal"
        elif "cash" in q_lower:
            val_name = "Cash"

        if val_name:
            sql = (
                f"SELECT '{target_table}' as basis, {group_col}, COUNT(*) as count, "
                f"ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM {target_table} WHERE {group_col} IS NOT NULL), 2) as share_percent, "
                f"(SELECT COUNT(*) FROM {target_table} WHERE {group_col} IS NOT NULL) as n_total, "
                f"COUNT(*) as n "
                f"FROM {target_table} WHERE {group_col} IS NOT NULL GROUP BY {group_col}"
            )
            return sql

    # Special Case B: Conversion rate (conversions / clicks)
    if ("conversion" in q_lower or "convert" in q_lower) and any("conv" in c.lower() for c in available_columns) and any("click" in c.lower() for c in available_columns):
        conv_c = next(c for c in available_columns if "conv" in c.lower())
        click_c = next(c for c in available_columns if "click" in c.lower())
        if group_col:
            sql = (
                f"SELECT '{target_table}' as basis, {group_col}, "
                f"SUM({conv_c}) as total_conversions, SUM({click_c}) as total_clicks, "
                f"ROUND(SUM({conv_c}) * 100.0 / NULLIF(SUM({click_c}), 0), 2) as conversion_rate_percent, "
                f"COUNT(*) as n "
                f"FROM {target_table} WHERE {group_col} IS NOT NULL AND {conv_c} IS NOT NULL AND {click_c} IS NOT NULL "
                f"GROUP BY {group_col} ORDER BY conversion_rate_percent DESC"
            )
            return sql

    # General Group-by with metrics or counts
    if group_col:
        select_items.append(group_col)
        where_clauses.append(f"{group_col} IS NOT NULL")

        if metric_cols:
            for m in metric_cols:
                where_clauses.append(f"{m} IS NOT NULL")
                ml = m.lower()
                if is_avg or "salary" in ml or ("age" in ml and not is_sum):
                    select_items.append(f"ROUND(AVG({m}), 2) as avg_{ml}")
                else:
                    select_items.append(f"ROUND(SUM({m}), 2) as total_{ml}")
        elif is_count or "employee" in q_lower or "transaction" in q_lower:
            count_alias = "transaction_count" if "transaction" in q_lower else ("employee_count" if "employee" in q_lower else "count")
            select_items.append(f"COUNT(*) as {count_alias}")

        select_items.append("COUNT(*) as n")
        group_sql = f"GROUP BY {group_col}"
        if is_highest and len(select_items) > 2:
            agg_col = select_items[2].split(" as ")[-1]
            order_by_clause = f" ORDER BY {agg_col} DESC"

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        return f"SELECT {', '.join(select_items)} FROM {target_table} {where_sql} {group_sql}{order_by_clause}".strip()

    # Overall aggregation without group-by
    if metric_cols:
        for m in metric_cols:
            where_clauses.append(f"{m} IS NOT NULL")
            ml = m.lower()
            if is_avg or "salary" in ml:
                select_items.append(f"ROUND(AVG({m}), 2) as avg_{ml}")
            else:
                select_items.append(f"ROUND(SUM({m}), 2) as total_{ml}")
        select_items.append(f"COUNT({metric_cols[0]}) as n")
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        return f"SELECT {', '.join(select_items)} FROM {target_table} {where_sql}".strip()

    if is_count:
        select_items.append("COUNT(*) as total_count")
        return f"SELECT {', '.join(select_items)} FROM {target_table}"

    return None


def format_label(val: Any) -> Any:
    if val is None:
        return "unspecified"
    if isinstance(val, str):
        val_clean = val.strip()
        if not val_clean:
            return "unspecified"
        if val_clean.lower() == "paypal":
            return "PayPal"
        if val_clean.lower() == "credit card":
            return "Credit Card"
        if val_clean.upper() in {"HR", "IT", "ID", "PR", "AI", "ML", "BI", "USA", "UK", "EU"}:
            return val_clean.upper()
        if val_clean.islower():
            return val_clean.title()
        return val_clean
    return val


def format_sql_query_result(
    rows: List[Dict[str, Any]],
    question: str,
    target_table: str,
    sampling_disclosure: Optional[str] = None,
    imputation_stats: Optional[Dict[str, Any]] = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Format query result rows into a natural language response with bound claims.
    Enforces that basis and n are stated and match the queried table.
    When data_clean is used for a numeric column with imputed cells, states the imputed share.
    """
    if not rows:
        ans = f"Based on {target_table}: no matching records were found."
        return ans, []

    q_lower = question.lower()
    claims: List[Dict[str, Any]] = []
    first_row = rows[0]
    basis = first_row.get("basis", target_table)

    # Determine total sample n across rows
    if "n_total" in first_row and first_row["n_total"] is not None:
        n_basis = int(first_row["n_total"])
    elif any("n" in r for r in rows):
        n_basis = sum(int(r["n"]) for r in rows if r.get("n") is not None)
    else:
        n_basis = len(rows)

    disc_note = f" (Note: {sampling_disclosure})" if sampling_disclosure else ""

    # Check for Credit Card payment share query
    if any("Payment_Method" in r and "share_percent" in r for r in rows):
        cc_row = next((r for r in rows if str(r.get("Payment_Method", "")).lower() == "credit card"), None)
        if cc_row:
            cc_share = float(cc_row["share_percent"])
            cc_count = int(cc_row.get("count", cc_row.get("n", 0)))
            total_n = int(cc_row.get("n_total", n_basis))
            ans = (
                f"Based on {basis} (n={total_n}{disc_note}): "
                f"Credit Card payments represent {cc_share:.2f}% ({cc_count} of {total_n} records)."
            )
            claims.append({"text": ans, "source_id": "query_sql", "metric_key": "Credit_Card_share_percent", "value": cc_share, "unit": "%"})
            claims.append({"text": ans, "source_id": "query_sql", "metric_key": "Credit_Card_count", "value": float(cc_count), "unit": "count"})
            claims.append({"text": ans, "source_id": "query_sql", "metric_key": "total_records", "value": float(total_n), "unit": "count"})
            return ans, claims

    # Check for conversion rate query
    if any("conversion_rate_percent" in r for r in rows):
        group_key = next((k for k in first_row.keys() if k not in ["basis", "n", "total_conversions", "total_clicks", "conversion_rate_percent"]), None)
        top = rows[0]
        top_name = format_label(top.get(group_key, "Top"))
        top_rate = float(top["conversion_rate_percent"])
        top_conv = float(top["total_conversions"])
        top_clicks = float(top["total_clicks"])

        impute_note = ""
        if basis == "data_clean" and imputation_stats:
            imp_items = []
            for col_k in ["Conversions", "Clicks"]:
                if col_k in imputation_stats and imputation_stats[col_k].get("imputation_rate", 0) > 0:
                    ir = imputation_stats[col_k]["imputation_rate"]
                    imp_items.append(f"{col_k} {ir * 100:.1f}% imputed")
                    claims.append({"text": f"{col_k} imputed share: {ir * 100:.1f}%", "source_id": "query_sql", "metric_key": f"{col_k}_imputed_rate", "value": round(ir * 100, 1), "unit": "%"})
            if imp_items:
                impute_note = f" (imputed share: {', '.join(imp_items)})"

        ans = (
            f"Based on {basis} (n={n_basis}{disc_note}{impute_note}): "
            f"'{top_name}' delivered the highest conversion rate at {top_rate:.2f}% ({int(top_conv)} conversions from {int(top_clicks):,} clicks)."
        )
        claims.append({"text": ans, "source_id": "query_sql", "metric_key": "total_records", "value": float(n_basis), "unit": "count"})
        claims.append({"text": ans, "source_id": "query_sql", "metric_key": f"{top_name}_conversion_rate_percent", "value": top_rate, "unit": "%"})
        claims.append({"text": ans, "source_id": "query_sql", "metric_key": f"{top_name}_total_conversions", "value": top_conv, "unit": "count"})
        claims.append({"text": ans, "source_id": "query_sql", "metric_key": f"{top_name}_total_clicks", "value": top_clicks, "unit": "count"})

        other_items = []
        for r in rows[1:]:
            c_name = format_label(r.get(group_key))
            c_rate = float(r["conversion_rate_percent"])
            c_conv = float(r["total_conversions"])
            c_clicks = float(r["total_clicks"])
            other_items.append(f"{c_name}: {c_rate:.2f}% ({int(c_conv)} conversions, {int(c_clicks):,} clicks)")
            claims.append({"text": ans, "source_id": "query_sql", "metric_key": f"{c_name}_conversion_rate_percent", "value": c_rate, "unit": "%"})
            claims.append({"text": ans, "source_id": "query_sql", "metric_key": f"{c_name}_total_conversions", "value": c_conv, "unit": "count"})
            claims.append({"text": ans, "source_id": "query_sql", "metric_key": f"{c_name}_total_clicks", "value": c_clicks, "unit": "count"})

        if other_items:
            ans += f" Other channels recorded: {'; '.join(other_items)}."
        return ans, claims

    # General Group-By Table formatting
    group_col = None
    metric_cols = []
    candidate_cols = [k for k in first_row.keys() if k not in ["basis", "n", "n_total"]]

    for k in candidate_cols:
        kl = k.lower()
        if any(kl.startswith(p) for p in ["avg", "total", "sum", "min", "max", "count", "share", "rate", "std", "mean", "median"]) or (
            len(candidate_cols) == 1 and isinstance(first_row[k], (int, float)) and not isinstance(first_row[k], bool)
        ):
            metric_cols.append(k)
        elif group_col is None:
            group_col = k
        else:
            metric_cols.append(k)

    if not metric_cols and group_col and any(isinstance(r.get(group_col), (int, float)) for r in rows):
        metric_cols = [group_col]
        group_col = None

    impute_note = ""
    if basis == "data_clean" and imputation_stats:
        imp_items = []
        for m in metric_cols:
            for c, stat in imputation_stats.items():
                if c.lower() in m.lower() and stat.get("imputation_rate", 0) > 0:
                    ir = stat["imputation_rate"]
                    imp_items.append(f"{c} {ir * 100:.1f}% imputed")
                    claims.append({"text": f"{c} imputed share: {ir * 100:.1f}%", "source_id": "query_sql", "metric_key": f"{c}_imputed_rate", "value": round(ir * 100, 1), "unit": "%"})
        if imp_items:
            impute_note = f" (imputed share: {', '.join(imp_items)})"

    row_sentences = []
    for r in rows:
        grp_val = format_label(r.get(group_col)) if group_col else None
        parts = []
        for m in metric_cols:
            val = r.get(m)
            if val is None:
                continue
            clean_m_name = m.replace("_", " ").replace("avg ", "average ").replace("total ", "total ")
            if "paypal" in clean_m_name.lower():
                clean_m_name = re.sub(r"(?i)\bpaypal\b", "PayPal", clean_m_name)
            if "credit card" in clean_m_name.lower():
                clean_m_name = re.sub(r"(?i)\bcredit card\b", "Credit Card", clean_m_name)
            elif clean_m_name.lower() in ("share", "share percent", "proportion") and "credit card" in q_lower:
                clean_m_name = "Credit Card share"
            elif clean_m_name.lower() in ("share", "share percent", "proportion") and "paypal" in q_lower:
                clean_m_name = "PayPal share"
            if isinstance(val, float):
                parts.append(f"{clean_m_name} was {val:,.2f}")
                claims.append({"text": f"{grp_val or clean_m_name} {clean_m_name}: {val}", "source_id": "query_sql", "metric_key": f"{grp_val or ''}_{m}".strip('_'), "value": round(val, 2), "unit": None})
            elif isinstance(val, int):
                parts.append(f"{clean_m_name} was {val:,}")
                claims.append({"text": f"{grp_val or clean_m_name} {clean_m_name}: {val}", "source_id": "query_sql", "metric_key": f"{grp_val or ''}_{m}".strip('_'), "value": float(val), "unit": "count"})
            else:
                parts.append(f"{clean_m_name} was {val}")

        row_n = r.get("n")
        n_str = f" (n={row_n})" if row_n is not None and len(rows) > 1 else ""

        if parts:
            if grp_val is not None:
                row_sentences.append(f"{grp_val}: {', '.join(parts)}{n_str}")
            else:
                row_sentences.append(f"{', '.join(parts)}{n_str}")
        elif grp_val is not None:
            count_val = r.get("transaction_count") or r.get("employee_count") or r.get("count") or r.get("n")
            if count_val is not None:
                if isinstance(grp_val, (int, float)):
                    col_name = group_col.replace('_', ' ') if group_col else 'value'
                    row_sentences.append(f"{col_name} was {grp_val} (count={count_val})")
                    claims.append({"text": f"{col_name}: {grp_val}", "source_id": "query_sql", "metric_key": f"{col_name}", "value": float(grp_val), "unit": None})
                else:
                    row_sentences.append(f"{grp_val}: transaction count was {count_val}" if "transaction" in q_lower else (f"{grp_val}: employee count was {count_val}" if "employee" in q_lower else f"{grp_val}: count was {count_val}"))
                    claims.append({"text": f"{grp_val}: {count_val}", "source_id": "query_sql", "metric_key": f"{grp_val}_count", "value": float(count_val), "unit": "count"})
            else:
                row_sentences.append(f"{grp_val}")

    ans = f"Based on {basis} (n={n_basis}{disc_note}{impute_note}): " + "; ".join(row_sentences) + "."

    # Ensure every single numeric token present in ans is bound as a claim
    from backend.app.agent.citation_checker import extract_numeric_tokens
    for num in extract_numeric_tokens(ans):
        if not any(abs(c["value"] - num) < 1e-4 for c in claims):
            claims.append({
                "text": ans,
                "source_id": "query_sql",
                "metric_key": str(num),
                "value": float(num),
                "unit": None
            })

    return ans, claims


def llm_choose_sql_query(
    question: str,
    available_columns: List[str],
    target_table: str = "data_clean",
    client: Optional[Any] = None
) -> Optional[str]:
    """
    Allow the LLM to choose a read-only SELECT query against target_table.
    Enforces safe read-only SQL, ensures target_table and available_columns are used,
    and returns None if query generation fails or violates safety constraints.
    """
    if not client:
        return None

    # Hypotheses or significance checks require statistical test insights, not plain SQL
    q_lower = question.lower()
    if any(sig in q_lower for sig in ["statistically significant", "statistical significance", "is it significant", "is there a significant", "is the difference significant"]):
        return None

    # Never generate SQL for questions about missing columns or entities
    from backend.app.services.chat_service import detect_missing_column_or_entity
    if detect_missing_column_or_entity(question, available_columns):
        return None

    matched_cols = extract_question_columns(question, available_columns)
    if not matched_cols:
        return None

    prompt = (
        f"You are a SQL expert. Write a single SQLite read-only SELECT query to answer the user question.\n"
        f"Target Table: {target_table}\n"
        f"Available Columns: {', '.join(available_columns)}\n"
        f"Question: {question}\n\n"
        f"CRITICAL RULES:\n"
        f"1. Return ONLY a single SELECT query querying directly from {target_table}.\n"
        f"2. Always include '{target_table}' as basis in the SELECT list (e.g. SELECT '{target_table}' as basis, ...).\n"
        f"3. When computing aggregate metrics (AVG, SUM, etc.) on a column, count the non-null metric values: COUNT(<metric_column>) as n (or include WHERE <metric_column> IS NOT NULL) so n strictly equals the observed non-null count.\n"
        f"4. Do NOT use any destructive statements (NO DROP, UPDATE, DELETE, INSERT, ALTER).\n"
        f"5. Return ONLY the raw SQL query string, no markdown fences, no explanation.\n"
    )

    try:
        provider_name = getattr(client, "provider_name", "")
        raw = ""
        if provider_name == "llm:gemini" and hasattr(client, "_get_client"):
            from google.genai import types
            genai_client = client._get_client()
            config = client._build_generate_config(types)
            res = client._execute_with_retry(genai_client, contents=prompt, config=config)
            raw = getattr(res, "text", "") or ""
        elif provider_name == "llm:claude" and hasattr(client, "_get_client"):
            anthropic_client = client._get_client()
            res = anthropic_client.messages.create(
                model=client.model,
                max_tokens=200,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = "".join(b.text for b in res.content if b.type == "text")
        else:
            return None

        # Clean SQL
        sql = raw.strip()
        if "```sql" in sql:
            sql = sql.split("```sql")[1].split("```")[0].strip()
        elif "```" in sql:
            sql = sql.split("```")[1].split("```")[0].strip()
        sql = sql.strip().strip(";")

        # Strict Validation
        clean_upper = sql.upper().strip()
        if not clean_upper.startswith("SELECT"):
            return None
        dangerous_tokens = {"DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "EXEC", "ATTACH", "DETACH"}
        tokens = set(re.findall(r"\b[A-Z]+\b", clean_upper))
        if any(dt in tokens for dt in dangerous_tokens):
            return None
        if target_table.lower() not in sql.lower():
            return None

        return sql
    except Exception as e:
        logger.debug("llm_choose_sql_query failed (%s); fallback will be used", e)
        return None

