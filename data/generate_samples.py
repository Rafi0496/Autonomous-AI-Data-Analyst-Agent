"""Script to generate 3 realistic, messy business datasets for testing & benchmarking:
1. Retail & E-commerce Sales
2. HR Employee Attrition
3. Digital Marketing Campaign Performance
"""
import os
import random
import pandas as pd
import numpy as np

def generate_datasets():
    os.makedirs("data/samples", exist_ok=True)
    os.makedirs("data/uploads", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("backend/tests/test_datasets", exist_ok=True)
    
    np.random.seed(42)
    random.seed(42)

    # 1. RETAIL SALES MESSY DATASET (~120 rows for rich testing)
    products = ["Laptop", "Wireless Mouse", "Keyboard", "USB-C Cable", "Monitor", "Headphones", "Webcam"]
    categories = ["Electronics ", "electronics", "Electronics", " Accessories", "Accessories  ", "Office Supplies"]
    regions = ["North", "South", "East", "West", "central", "CENTRAL", None]
    date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"]
    
    retail_rows = []
    base_dates = pd.date_range("2025-01-01", periods=100, freq="D")
    
    for i in range(120):
        # Deliberate messiness: mixed dates, string numbers with '$', missing values, whitespace
        dt = random.choice(base_dates)
        fmt = random.choice(date_formats)
        date_str = dt.strftime(fmt)
        
        prod = random.choice(products)
        cat = random.choice(categories)
        reg = random.choice(regions)
        
        # 10% chance of missing price, 5% formatted with '$'
        if random.random() < 0.10:
            unit_price = np.nan
        elif random.random() < 0.30:
            unit_price = f"${random.uniform(15.0, 850.0):.2f}"
        else:
            unit_price = round(random.uniform(15.0, 850.0), 2)
            
        qty = random.choice([1, 2, 3, 4, 5, 10, -1, 999, None]) # outlier & negative & null
        cust_id = f"CUST-{random.randint(100, 150)}" if random.random() > 0.08 else None
        
        retail_rows.append({
            "Transaction_ID": f"TXN-{1000 + i}",
            "Date": date_str,
            "Customer_ID": cust_id,
            "Product": prod,
            "Category": cat,
            "Region": reg,
            "Quantity": qty,
            "Unit_Price": unit_price,
            "Payment_Method": random.choice(["Credit Card", "PayPal", "Debit Card", "credit card", None])
        })
    
    retail_df = pd.DataFrame(retail_rows)
    # Add 8 duplicate rows to test duplicate handling
    duplicates = retail_df.iloc[[5, 12, 25, 40]].copy()
    duplicates2 = retail_df.iloc[[12, 40]].copy()
    retail_df = pd.concat([retail_df, duplicates, duplicates2], ignore_index=True)
    
    retail_path = "data/samples/retail_sales_messy.csv"
    retail_df.to_csv(retail_path, index=False)
    retail_df.to_csv("backend/tests/test_datasets/retail_sales_messy.csv", index=False)
    print(f"Generated {retail_path}: {retail_df.shape[0]} rows, {retail_df.shape[1]} columns")

    # 2. HR ATTRITION MESSY DATASET
    departments = ["Sales", "sales", "SALES", "Engineering", "engineering", "HR", "Marketing", "marketing", None]
    genders = ["Male", "Female", "M", "F", "Other", None]
    
    hr_rows = []
    for i in range(110):
        age = random.choice([22, 28, 35, 42, 50, 62, 150, None]) # 150 is outlier
        dept = random.choice(departments)
        salary = random.choice([
            None,
            f"${random.randint(45000, 180000)}",
            random.randint(45000, 180000),
            -5000 # invalid salary outlier
        ])
        tenure = random.choice([0.5, 1.2, 3.0, 5.5, 10.0, None])
        attrition = random.choice(["Yes", "No", "yes", "no", None])
        perf_score = random.choice([1, 2, 3, 4, 5, None])
        satisfaction = random.choice(["Low", "Medium", "High", "very high", " High ", None])
        
        hr_rows.append({
            "Employee_ID": f"EMP-{500 + i}",
            "Age": age,
            "Gender": random.choice(genders),
            "Department": dept,
            "Annual_Salary": salary,
            "Tenure_Years": tenure,
            "Satisfaction_Level": satisfaction,
            "Performance_Score": perf_score,
            "Attrition": attrition,
            "Last_Promotion_Year": random.choice(["2020", "2021", "2022", "2023", "N/A", "None", None])
        })
    
    hr_df = pd.DataFrame(hr_rows)
    # Add duplicates
    hr_df = pd.concat([hr_df, hr_df.iloc[[2, 10, 15]]], ignore_index=True)
    hr_path = "data/samples/hr_attrition_messy.csv"
    hr_df.to_csv(hr_path, index=False)
    hr_df.to_csv("backend/tests/test_datasets/hr_attrition_messy.csv", index=False)
    print(f"Generated {hr_path}: {hr_df.shape[0]} rows, {hr_df.shape[1]} columns")

    # 3. MARKETING CAMPAIGN MESSY DATASET
    channels = ["Google Ads", "Facebook", "Instagram", "google ads", "LinkedIn", " Email ", None]
    mkt_rows = []
    for i in range(100):
        spend = random.choice([
            f"${random.uniform(200, 5000):.2f}",
            round(random.uniform(200, 5000), 2),
            None
        ])
        impressions = random.choice([1000, 5000, 20000, 80000, None, 0])
        clicks = random.choice([10, 50, 300, 1200, None, 0])
        conversions = random.choice([1, 5, 25, 90, None, 0])
        camp_date = random.choice(["2025-03-01", "03/05/2025", "10-03-2025", "InvalidDate", None])
        
        mkt_rows.append({
            "Campaign_ID": f"CAMP-{i+1}",
            "Date": camp_date,
            "Channel": random.choice(channels),
            "Ad_Spend": spend,
            "Impressions": impressions,
            "Clicks": clicks,
            "Conversions": conversions,
            "Target_Audience": random.choice(["B2B", "B2C", "Retargeting", "b2c", None])
        })
    
    mkt_df = pd.DataFrame(mkt_rows)
    mkt_df = pd.concat([mkt_df, mkt_df.iloc[[3, 8]]], ignore_index=True)
    mkt_path = "data/samples/marketing_campaign_messy.csv"
    mkt_df.to_csv(mkt_path, index=False)
    mkt_df.to_csv("backend/tests/test_datasets/marketing_campaign_messy.csv", index=False)
    print(f"Generated {mkt_path}: {mkt_df.shape[0]} rows, {mkt_df.shape[1]} columns")

if __name__ == "__main__":
    generate_datasets()
