"""Create small sample fixtures for E2E Multi-Format testing."""
import json
from pathlib import Path
import pandas as pd
import zipfile
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

fixture_dir = Path("data/e2e_fixtures")
fixture_dir.mkdir(parents=True, exist_ok=True)

# 1. Excel (.xlsx)
df_excel = pd.DataFrame({
    "Product": ["Wireless Mouse", "Mechanical Keyboard", "USB-C Hub", "27-inch Monitor"],
    "Category": ["Accessories", "Accessories", "Cables", "Displays"],
    "Units_Sold": [140, 85, 210, 45],
    "Unit_Price": [24.99, 79.99, 34.50, 249.99],
    "Revenue": [3498.60, 6799.15, 7245.00, 11249.55]
})
excel_path = fixture_dir / "sample_sales.xlsx"
df_excel.to_excel(excel_path, index=False)
print("Created", excel_path)

# 2. JSON (.json)
json_data = [
    {"user_id": 101, "name": "Alice Smith", "department": "Marketing", "campaigns": 5, "spend": 4500.0},
    {"user_id": 102, "name": "Bob Jones", "department": "Engineering", "campaigns": 2, "spend": 1200.0},
    {"user_id": 103, "name": "Carol Taylor", "department": "Sales", "campaigns": 8, "spend": 9800.0},
    {"user_id": 104, "name": "David Clark", "department": "Finance", "campaigns": 3, "spend": 3100.0}
]
json_path = fixture_dir / "sample_marketing.json"
json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
print("Created", json_path)

# 3. XML (.xml)
xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<inventory>
  <item>
    <sku>SKU-001</sku>
    <title>Ergonomic Chair</title>
    <stock>45</stock>
    <cost>189.50</cost>
  </item>
  <item>
    <sku>SKU-002</sku>
    <title>Standing Desk</title>
    <stock>22</stock>
    <cost>349.00</cost>
  </item>
  <item>
    <sku>SKU-003</sku>
    <title>Monitor Arm</title>
    <stock>80</stock>
    <cost>49.99</cost>
  </item>
</inventory>
"""
xml_path = fixture_dir / "sample_inventory.xml"
xml_path.write_text(xml_content, encoding="utf-8")
print("Created", xml_path)

# 4. Parquet (.parquet)
df_parquet = pd.DataFrame({
    "patient_id": [1001, 1002, 1003, 1004],
    "age": [28, 45, 62, 35],
    "blood_pressure": [118, 134, 142, 122],
    "bmi": [22.4, 28.1, 31.0, 24.6],
    "glucose_level": [92, 110, 145, 98]
})
parquet_path = fixture_dir / "sample_clinical.parquet"
df_parquet.to_parquet(parquet_path, index=False)
print("Created", parquet_path)

# 5. PDF with structured table (.pdf)
pdf_path = fixture_dir / "sample_report_table.pdf"
doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
styles = getSampleStyleSheet()
story = [
    Paragraph("Quarterly Financial Performance Summary", styles["Heading1"]),
    Spacer(1, 12),
    Paragraph("The table below outlines segment revenue and margin performance:", styles["Normal"]),
    Spacer(1, 12)
]
table_data = [
    ["Quarter", "Region", "Revenue ($M)", "Growth (%)", "Operating Margin (%)"],
    ["Q1", "North America", "45.2", "12.4", "22.5"],
    ["Q2", "North America", "48.1", "14.1", "24.0"],
    ["Q3", "EMEA", "32.6", "8.9", "18.2"],
    ["Q4", "APAC", "28.4", "19.5", "21.1"]
]
t = Table(table_data)
t.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.grey),
    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ('BOTTOMPADDING', (0,0), (-1,0), 6),
    ('GRID', (0,0), (-1,-1), 1, colors.black),
]))
story.append(t)
doc.build(story)
print("Created", pdf_path)

# 6. ZIP archive (.zip)
zip_path = fixture_dir / "sample_archive.zip"
with zipfile.ZipFile(zip_path, "w") as zf:
    zf.writestr("customers.csv", "id,name,tier,spend\n1,Alice,Platinum,5200\n2,Bob,Gold,3100\n3,Charlie,Silver,1400\n")
print("Created", zip_path)
