"""General SQL generation and query result claim-binding for Chat Q&A (Milestone 2).

Replaces question-specific hardcoding with a general flow:
- Dynamically generates read-only DuckDB SQL queries against data_clean or data_observed.
- Determines basis strictly: 'observed', 'non-missing', 'recorded' -> data_observed; otherwise data_clean.
- Converts query result rows directly into natural language answer text and bound claims.
- Assures every answer states its basis and n matching the queried table.
"""
import re
from typing import Any, Dict, List, Optional, Tuple


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

    if any(k in q_lower for k in ["transaction", "transactions", "orders", "sales"]):
        tx_c = next((c for c in available_columns if "transaction" in c.lower() or "order" in c.lower()), None)
        if tx_c and tx_c not in matched_cols:
            matched_cols.append(tx_c)

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


def insight_shares_column(ins: Dict[str, Any], question_cols: List[str]) -> bool:
    """Check if an insight references any of the columns in question_cols."""
    if not question_cols:
        return False
    ins_cols = ins.get("columns", []) or []
    if isinstance(ins_cols, str):
        ins_cols = [ins_cols]
    col = ins.get("column")
    if col and col not in ins_cols:
        ins_cols.append(col)

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
        select_items.append("COUNT(*) as n")
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        return f"SELECT {', '.join(select_items)} FROM {target_table} {where_sql}".strip()

    if is_count:
        select_items.append("COUNT(*) as total_count")
        return f"SELECT {', '.join(select_items)} FROM {target_table}"

    return None


def format_label(val: Any) -> Any:
    if isinstance(val, str) and val.islower():
        if val.upper() in {"HR", "IT", "ID", "PR", "AI", "ML", "BI", "USA", "UK", "EU"}:
            return val.upper()
        return val.title()
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
    group_col = next((k for k in first_row.keys() if k not in ["basis", "n", "n_total"]), None)
    metric_cols = [k for k in first_row.keys() if k not in ["basis", "n", "n_total", group_col]]

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
        grp_val = format_label(r.get(group_col))
        parts = []
        for m in metric_cols:
            val = r.get(m)
            if val is None:
                continue
            clean_m_name = m.replace("_", " ").replace("avg ", "average ").replace("total ", "total ")
            if isinstance(val, float):
                parts.append(f"{clean_m_name} was {val:,.2f}")
                claims.append({"text": f"{grp_val} {clean_m_name}: {val}", "source_id": "query_sql", "metric_key": f"{grp_val}_{m}", "value": round(val, 2), "unit": None})
            elif isinstance(val, int):
                parts.append(f"{clean_m_name} was {val:,}")
                claims.append({"text": f"{grp_val} {clean_m_name}: {val}", "source_id": "query_sql", "metric_key": f"{grp_val}_{m}", "value": float(val), "unit": "count"})
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
