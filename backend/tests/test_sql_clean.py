"""Unit tests for query_sql on cleaned data (Item 2)."""
import pytest
from backend.app.services.sql_tool import query_sql

def test_query_sql_on_cleaned_data_excludes_999():
    """
    Test: SUM(Quantity) on retail must not include any 999 sentinel placeholder values.
    Verify that query_sql executes over cleaned data and exposes both data_clean and data_observed.
    """
    # 1. Query over data_clean
    res_clean = query_sql("retail_sales_messy.csv", "SELECT SUM(Quantity) as total_qty FROM data_clean")
    total_qty_clean = res_clean["rows"][0]["total_qty"]
    # In raw data, SUM(Quantity) was 16,300 with sentinels (and 9,175 in Electronics).
    # In cleaned data, Quantity sentinels (999.0) are converted to NULL and imputed (total 384).
    assert total_qty_clean < 1000.0, f"Expected total_qty < 1000 without 999s, got {total_qty_clean}"
    assert total_qty_clean == pytest.approx(384.0, abs=1.0)

    # 2. Query over data_observed (non-imputed only)
    res_obs = query_sql("retail_sales_messy.csv", "SELECT SUM(Quantity) as total_qty FROM data_observed")
    total_qty_obs = res_obs["rows"][0]["total_qty"]
    assert total_qty_obs == pytest.approx(288.0, abs=1.0)

    # 3. Query category level on data_clean: Electronics sum must not be 9,175
    res_cat = query_sql(
        "retail_sales_messy.csv",
        "SELECT Category, SUM(Quantity) as cat_qty FROM data_clean GROUP BY Category ORDER BY Category"
    )
    rows_by_cat = {r["Category"]: r["cat_qty"] for r in res_cat["rows"]}
    assert "Electronics" in rows_by_cat
    electronics_qty = rows_by_cat["Electronics"]
    assert electronics_qty < 500.0, f"Electronics sum should not include 999 sentinels, got {electronics_qty}"
    assert electronics_qty == pytest.approx(204.0, abs=1.0)
    print(f"Corrected Electronics Quantity sum replacing 9,175 is: {electronics_qty}")

    # 4. Backward-compatible table alias 'df'
    res_df = query_sql("retail_sales_messy.csv", "SELECT SUM(Quantity) as total_qty FROM df")
    assert res_df["rows"][0]["total_qty"] == pytest.approx(384.0, abs=1.0)
