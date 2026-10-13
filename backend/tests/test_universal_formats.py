"""Unit tests for Universal Multi-Format Ingestion & Parsers."""
import io
import json
import sqlite3
import tempfile
import zipfile
import gzip
from pathlib import Path
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.file_parser import UniversalFileParser

client = TestClient(app)


def test_parser_csv(tmp_path):
    f = tmp_path / "test.csv"
    f.write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8")
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.csv")
    assert fmt == "csv"
    assert is_tab is True
    assert df.shape == (2, 3)


def test_parser_tsv(tmp_path):
    f = tmp_path / "test.tsv"
    f.write_text("col1\tcol2\n10\t20\n30\t40\n", encoding="utf-8")
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.tsv")
    assert fmt == "csv"
    assert is_tab is True
    assert df.shape == (2, 2)


def test_parser_txt_pipe_delimited(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("id|name|score\n1|Alice|95\n2|Bob|88\n", encoding="utf-8")
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.txt")
    assert is_tab is True
    assert df.shape == (2, 3)


def test_parser_excel(tmp_path):
    f = tmp_path / "test.xlsx"
    df_in = pd.DataFrame({"product": ["A", "B"], "sales": [100, 200]})
    df_in.to_excel(f, index=False)
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.xlsx")
    assert fmt == "excel"
    assert is_tab is True
    assert df.shape == (2, 2)


def test_parser_json_records(tmp_path):
    f = tmp_path / "test.json"
    data = [{"id": 1, "val": "x"}, {"id": 2, "val": "y"}]
    f.write_text(json.dumps(data), encoding="utf-8")
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.json")
    assert fmt == "json"
    assert is_tab is True
    assert df.shape == (2, 2)


def test_parser_jsonl(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text('{"id": 1, "k": "a"}\n{"id": 2, "k": "b"}\n', encoding="utf-8")
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.jsonl")
    assert fmt == "jsonl"
    assert is_tab is True
    assert df.shape == (2, 2)


def test_parser_html_table(tmp_path):
    f = tmp_path / "test.html"
    f.write_text("<html><body><table><tr><th>X</th><th>Y</th></tr><tr><td>1</td><td>2</td></tr><tr><td>3</td><td>4</td></tr></table></body></html>", encoding="utf-8")
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.html")
    assert fmt == "html"
    assert is_tab is True
    assert df.shape == (2, 2)


def test_parser_xml(tmp_path):
    f = tmp_path / "test.xml"
    f.write_text("<data><row><id>1</id><val>10</val></row><row><id>2</id><val>20</val></row></data>", encoding="utf-8")
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.xml")
    assert fmt == "xml"
    assert is_tab is True
    assert df.shape == (2, 2)


def test_parser_parquet(tmp_path):
    f = tmp_path / "test.parquet"
    df_in = pd.DataFrame({"feature1": [1.1, 2.2], "feature2": [3.3, 4.4]})
    df_in.to_parquet(f, index=False)
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.parquet")
    assert fmt == "parquet"
    assert is_tab is True
    assert df.shape == (2, 2)


def test_parser_feather(tmp_path):
    f = tmp_path / "test.feather"
    df_in = pd.DataFrame({"num": [10, 20], "tag": ["alpha", "beta"]})
    df_in.to_feather(f)
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.feather")
    assert fmt == "feather"
    assert is_tab is True
    assert df.shape == (2, 2)


def test_parser_sqlite(tmp_path):
    f = tmp_path / "test.sqlite"
    conn = sqlite3.connect(f)
    conn.execute("CREATE TABLE metrics (metric_name TEXT, metric_value REAL)")
    conn.execute("INSERT INTO metrics VALUES ('m1', 12.5), ('m2', 34.8)")
    conn.commit()
    conn.close()
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.sqlite")
    assert fmt == "sqlite"
    assert is_tab is True
    assert df.shape == (2, 2)


def test_parser_docx_table(tmp_path):
    import docx
    f = tmp_path / "test.docx"
    doc = docx.Document()
    table = doc.add_table(rows=3, cols=2)
    table.rows[0].cells[0].text = "HeaderA"
    table.rows[0].cells[1].text = "HeaderB"
    table.rows[1].cells[0].text = "val1"
    table.rows[1].cells[1].text = "val2"
    table.rows[2].cells[0].text = "val3"
    table.rows[2].cells[1].text = "val4"
    doc.save(f)

    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.docx")
    assert fmt == "docx"
    assert is_tab is True
    assert df.shape == (2, 2)


def test_parser_zip_archive(tmp_path):
    f = tmp_path / "test.zip"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("nested.csv", "x,y,z\n1,2,3\n4,5,6\n")
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.zip")
    assert fmt == "zip"
    assert is_tab is True
    assert df.shape == (2, 3)


def test_parser_gzip(tmp_path):
    f = tmp_path / "test.csv.gz"
    with gzip.open(f, "wb") as gz:
        gz.write(b"colA,colB\n100,200\n300,400\n")
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "test.csv.gz")
    assert fmt == "gzip"
    assert is_tab is True
    assert df.shape == (2, 2)


def test_parser_non_tabular_fallback(tmp_path):
    f = tmp_path / "sample_image.png"
    # Write a dummy PNG header/bytes
    f.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4")
    df, fmt, is_tab, desc = UniversalFileParser.parse_file(f, "sample_image.png")
    assert fmt == "binary_fallback"
    assert is_tab is False
    assert "could not find tabular data" in desc
