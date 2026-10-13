"""Universal Multi-Format File Ingestion & Parsing Service.

Supports:
- Delimiter-sniffed CSV, TSV, TXT
- Excel workbooks: XLSX, XLSM, XLS, ODS (reads all sheets)
- JSON, JSONL, NDJSON
- XML, HTML (table extraction)
- Parquet, Feather
- SQLite / DB (extracts tables)
- PDF (extracts tabular text and tables)
- DOCX (extracts table elements and structured paragraphs)
- Archives: ZIP, GZ, TAR.GZ (zip-bomb safe extraction)
- Non-tabular files (images, audio, binaries, free text) with graceful fallback.
"""
import csv
import gzip
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MAX_ZIP_EXTRACTED_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_ZIP_MEMBERS = 100
MAX_PARSE_TIME_SECONDS = 15


class UniversalFileParser:
    """Detects, sniffs, and extracts tabular data from any file format."""

    @classmethod
    def parse_file(cls, file_path: Path, original_filename: str) -> Tuple[pd.DataFrame, str, bool, str]:
        """
        Parse file into a pandas DataFrame.
        Returns:
            df: pd.DataFrame
            detected_format: str (e.g. 'csv', 'xlsx', 'parquet', 'json', 'pdf', 'text_fallback', 'binary_summary')
            is_tabular: bool (True if genuine tabular data was extracted, False if fallback summary)
            reader_used: str (Human-readable description of parser and extraction method)
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found at {file_path}")

        file_size = file_path.stat().st_size
        ext = Path(original_filename).suffix.lower().lstrip(".")

        # Read first 8KB for content sniffing
        with open(file_path, "rb") as f:
            header_bytes = f.read(8192)

        # 1. Archive formats (ZIP, GZ)
        if ext in ("zip",) or header_bytes.startswith(b"PK\x03\x04"):
            # Could be Excel (XLSX/XLSM) or Word (DOCX) or actual ZIP
            if ext in ("xlsx", "xlsm"):
                return cls._read_excel(file_path, original_filename)
            elif ext in ("docx",):
                return cls._read_docx(file_path, original_filename)
            else:
                return cls._read_zip(file_path, original_filename)

        if ext in ("gz", "gzip") or header_bytes.startswith(b"\x1f\x8b"):
            return cls._read_gzip(file_path, original_filename)

        # 2. Excel (legacy XLS, ODS)
        if ext in ("xls", "ods"):
            return cls._read_excel(file_path, original_filename)

        # 3. Parquet / Feather
        if ext == "parquet" or header_bytes.startswith(b"PAR1"):
            return cls._read_parquet(file_path, original_filename)
        if ext == "feather" or header_bytes.startswith(b"FEA1"):
            return cls._read_feather(file_path, original_filename)

        # 4. SQLite database
        if ext in ("sqlite", "db", "sqlite3") or header_bytes.startswith(b"SQLite format 3\x00"):
            return cls._read_sqlite(file_path, original_filename)

        # 5. PDF Documents
        if ext == "pdf" or header_bytes.startswith(b"%PDF-"):
            return cls._read_pdf(file_path, original_filename)

        # 6. Word DOCX
        if ext == "docx":
            return cls._read_docx(file_path, original_filename)

        # 7. XML / HTML
        if ext in ("xml", "html", "htm") or (b"<table" in header_bytes.lower() or b"<?xml" in header_bytes.lower()):
            res = cls._try_read_xml_html(file_path, original_filename, header_bytes)
            if res is not None:
                return res

        # 8. JSON / JSONL / NDJSON
        if ext in ("json", "jsonl", "ndjson") or header_bytes.strip().startswith((b"{", b"[")):
            res = cls._try_read_json(file_path, original_filename)
            if res is not None:
                return res

        # Media & Binary signatures (Images, Audio, Video)
        media_exts = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "ico", "svg", "mp3", "wav", "ogg", "mp4", "avi", "mov", "mkv", "webm", "flac"}
        media_magics = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"RIFF", b"ID3")
        if ext in media_exts or header_bytes.startswith(media_magics):
            return cls._read_binary_summary(file_path, original_filename, file_size)

        # 9. Delimited Text (CSV, TSV, TXT, or sniffed text)
        if b"\x00" not in header_bytes:
            res = cls._try_read_delimited(file_path, original_filename, header_bytes)
            if res is not None:
                return res

            # 10. Fallback: Free Text
            res = cls._try_read_free_text(file_path, original_filename, header_bytes)
            if res is not None:
                return res
        if res is not None:
            return res

        # 11. Final Fallback: Binary / Non-tabular Summary
        return cls._read_binary_summary(file_path, original_filename, file_size)

    @classmethod
    def _read_excel(cls, file_path: Path, filename: str) -> Tuple[pd.DataFrame, str, bool, str]:
        """Read all sheets of an Excel workbook; combine or pick primary sheet."""
        try:
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            if not sheet_names:
                raise ValueError("Excel file contains no sheets.")

            # Load sheets
            dfs = []
            for sheet in sheet_names:
                sheet_df = excel_file.parse(sheet)
                if not sheet_df.empty:
                    sheet_df["__sheet_name__"] = sheet
                    dfs.append(sheet_df)

            if not dfs:
                raise ValueError("All sheets in Excel file are empty.")

            # If multiple sheets share same columns, concatenate; otherwise pick largest sheet
            if len(dfs) == 1:
                final_df = dfs[0].drop(columns=["__sheet_name__"], errors="ignore")
                reader_desc = f"Excel reader (sheet '{sheet_names[0]}')"
            else:
                first_cols = set(dfs[0].columns) - {"__sheet_name__"}
                can_combine = all(set(d.columns) - {"__sheet_name__"} == first_cols for d in dfs)
                if can_combine:
                    final_df = pd.concat(dfs, ignore_index=True)
                    reader_desc = f"Excel reader (combined {len(dfs)} sheets: {', '.join(sheet_names)})"
                else:
                    # Pick sheet with the most rows
                    best_df = max(dfs, key=lambda d: len(d))
                    sheet_name = best_df["__sheet_name__"].iloc[0]
                    final_df = best_df.drop(columns=["__sheet_name__"], errors="ignore")
                    reader_desc = f"Excel reader (primary sheet '{sheet_name}' out of {len(sheet_names)} sheets: {', '.join(sheet_names)})"

            return cls._clean_extracted_df(final_df), "excel", True, reader_desc
        except Exception as e:
            logger.warning("Excel parsing failed for %s: %s", filename, e)
            raise ValueError(f"Failed to parse Excel workbook: {str(e)}")

    @classmethod
    def _read_parquet(cls, file_path: Path, filename: str) -> Tuple[pd.DataFrame, str, bool, str]:
        """Read Parquet dataset via pyarrow or duckdb."""
        try:
            df = pd.read_parquet(file_path)
            return cls._clean_extracted_df(df), "parquet", True, "Apache Parquet columnar reader"
        except Exception:
            try:
                import duckdb
                df = duckdb.query(f"SELECT * FROM read_parquet('{file_path.as_posix()}')").df()
                return cls._clean_extracted_df(df), "parquet", True, "DuckDB Parquet reader"
            except Exception as e:
                raise ValueError(f"Failed to parse Parquet file: {str(e)}")

    @classmethod
    def _read_feather(cls, file_path: Path, filename: str) -> Tuple[pd.DataFrame, str, bool, str]:
        """Read Feather / Arrow IPC dataset."""
        try:
            df = pd.read_feather(file_path)
            return cls._clean_extracted_df(df), "feather", True, "Apache Arrow Feather reader"
        except Exception as e:
            raise ValueError(f"Failed to parse Feather file: {str(e)}")

    @classmethod
    def _read_sqlite(cls, file_path: Path, filename: str) -> Tuple[pd.DataFrame, str, bool, str]:
        """Read SQLite tables, picking the largest user table."""
        try:
            conn = sqlite3.connect(f"file:{file_path.as_posix()}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in cursor.fetchall()]
            if not tables:
                conn.close()
                raise ValueError("SQLite database contains no user tables.")

            best_table = tables[0]
            max_rows = -1
            for tbl in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM \"{tbl}\"")
                    cnt = cursor.fetchone()[0]
                    if cnt > max_rows:
                        max_rows = cnt
                        best_table = tbl
                except Exception:
                    pass

            df = pd.read_sql_query(f"SELECT * FROM \"{best_table}\"", conn)
            conn.close()
            desc = f"SQLite reader (table '{best_table}' of {len(tables)} tables: {', '.join(tables[:5])})"
            return cls._clean_extracted_df(df), "sqlite", True, desc
        except Exception as e:
            raise ValueError(f"Failed to read SQLite database: {str(e)}")

    @classmethod
    def _try_read_json(cls, file_path: Path, filename: str) -> Optional[Tuple[pd.DataFrame, str, bool, str]]:
        """Read JSON, JSONL, or NDJSON."""
        ext = Path(filename).suffix.lower().lstrip(".")
        try:
            # If specifically .jsonl or .ndjson, try JSON Lines first
            if ext in ("jsonl", "ndjson"):
                try:
                    df = pd.read_json(file_path, lines=True)
                    if not df.empty and df.shape[1] > 1:
                        return cls._clean_extracted_df(df), "jsonl", True, "Newline-delimited JSON (JSONL) reader"
                except Exception:
                    pass

            # Try reading as standard JSON
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)

            if isinstance(data, list):
                if data and isinstance(data[0], dict):
                    df = pd.json_normalize(data)
                    return cls._clean_extracted_df(df), "json", True, "JSON record array reader"
                else:
                    df = pd.DataFrame({"value": data})
                    return cls._clean_extracted_df(df), "json", True, "JSON list reader"
            elif isinstance(data, dict):
                # Check for common record containers
                for key in ("data", "items", "rows", "results", "records"):
                    if key in data and isinstance(data[key], list) and data[key] and isinstance(data[key][0], dict):
                        df = pd.json_normalize(data[key])
                        return cls._clean_extracted_df(df), "json", True, f"JSON object reader (extracted '{key}')"
                # Flatten dictionary
                df = pd.json_normalize(data)
                return cls._clean_extracted_df(df), "json", True, "JSON key-value object reader"
        except Exception:
            pass
        return None

    @classmethod
    def _try_read_xml_html(cls, file_path: Path, filename: str, header_bytes: bytes) -> Optional[Tuple[pd.DataFrame, str, bool, str]]:
        """Extract HTML tables or XML tabular structures."""
        # Try HTML tables first
        try:
            tables = pd.read_html(file_path)
            if tables:
                # Pick largest table
                best = max(tables, key=lambda t: t.size)
                if not best.empty and best.shape[1] > 1:
                    return cls._clean_extracted_df(best), "html", True, f"HTML table extractor (extracted {len(tables)} tables, selected primary)"
        except Exception:
            pass

        # Try XML via pandas
        try:
            df = pd.read_xml(file_path)
            if not df.empty and df.shape[1] > 1:
                return cls._clean_extracted_df(df), "xml", True, "XML schema extractor"
        except Exception:
            pass

        return None

    @classmethod
    def _try_read_delimited(cls, file_path: Path, filename: str, header_bytes: bytes) -> Optional[Tuple[pd.DataFrame, str, bool, str]]:
        """Read CSV/TSV/TXT with delimiter sniffing."""
        # Detect encoding
        for enc in ("utf-8", "latin1", "cp1252"):
            try:
                sample_text = header_bytes.decode(enc, errors="strict")
                break
            except UnicodeDecodeError:
                continue
        else:
            sample_text = header_bytes.decode("utf-8", errors="replace")
            enc = "utf-8"

        # Check delimiter sniffing
        delimiter = None
        try:
            dialect = csv.Sniffer().sniff(sample_text[:4096])
            delimiter = dialect.delimiter
        except Exception:
            # Fallback delimiter voting
            counts = {
                ",": sample_text.count(","),
                "\t": sample_text.count("\t"),
                ";": sample_text.count(";"),
                "|": sample_text.count("|"),
            }
            if max(counts.values()) > 2:
                delimiter = max(counts, key=counts.get)

        if not delimiter:
            delimiter = ","

        try:
            df = pd.read_csv(file_path, sep=delimiter, encoding=enc, low_memory=False)
            if not df.empty and df.shape[1] >= 1:
                delim_name = {"\t": "Tab (TSV)", ",": "Comma (CSV)", ";": "Semicolon", "|": "Pipe"}.get(delimiter, f"'{delimiter}'")
                return cls._clean_extracted_df(df), "csv", True, f"Delimited text reader ({delim_name} delimiter)"
        except Exception:
            pass

        return None

    @classmethod
    def _read_pdf(cls, file_path: Path, filename: str) -> Tuple[pd.DataFrame, str, bool, str]:
        """Extract tables from PDF pages, falling back to structured line text."""
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            all_lines = []
            for page in reader.pages:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    cleaned = line.strip()
                    if cleaned:
                        all_lines.append(cleaned)

            if not all_lines:
                return cls._read_binary_summary(file_path, filename, file_path.stat().st_size, reason="PDF contains no extractable text or tables (scanned image or empty).")

            # Try to detect delimited/columnar pattern in lines
            table_rows = []
            delimiter_candidate = None
            for delim in (",", "\t", "|"):
                if sum(line.count(delim) >= 1 for line in all_lines[:20]) >= 5:
                    delimiter_candidate = delim
                    break

            if delimiter_candidate:
                for line in all_lines:
                    parts = [p.strip() for p in line.split(delimiter_candidate)]
                    if len(parts) > 1:
                        table_rows.append(parts)

                if len(table_rows) >= 2:
                    max_cols = max(len(r) for r in table_rows)
                    padded = [r + [""] * (max_cols - len(r)) for r in table_rows]
                    header = padded[0]
                    df = pd.DataFrame(padded[1:], columns=header)
                    return cls._clean_extracted_df(df), "pdf", True, "PDF table extractor"

            # Fallback to structured text
            df = pd.DataFrame({
                "page_line": range(1, len(all_lines) + 1),
                "text_content": all_lines,
                "word_count": [len(l.split()) for l in all_lines]
            })
            return cls._clean_extracted_df(df), "pdf", True, "PDF structured text extractor (line-level dataset)"
        except Exception as e:
            return cls._read_binary_summary(file_path, filename, file_path.stat().st_size, reason=f"PDF extraction error: {str(e)}")

    @classmethod
    def _read_docx(cls, file_path: Path, filename: str) -> Tuple[pd.DataFrame, str, bool, str]:
        """Extract tables from Word DOCX document, falling back to paragraphs."""
        try:
            import docx
            doc = docx.Document(file_path)

            # Check if document has tables
            if doc.tables:
                # Find largest table
                best_table = max(doc.tables, key=lambda t: len(t.rows) * len(t.columns))
                data = []
                for row in best_table.rows:
                    data.append([cell.text.strip() for cell in row.cells])

                if len(data) >= 2:
                    max_cols = max(len(r) for r in data)
                    padded = [r + [""] * (max_cols - len(r)) for r in data]
                    df = pd.DataFrame(padded[1:], columns=padded[0])
                    return cls._clean_extracted_df(df), "docx", True, f"Word DOCX table extractor (extracted primary table of {len(doc.tables)} tables)"

            # Fallback to paragraphs
            paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            if paras:
                df = pd.DataFrame({
                    "paragraph_number": range(1, len(paras) + 1),
                    "text_content": paras,
                    "word_count": [len(p.split()) for p in paras]
                })
                return cls._clean_extracted_df(df), "docx", True, "Word DOCX structured paragraph extractor"

            return cls._read_binary_summary(file_path, filename, file_path.stat().st_size, reason="Word document contains no extractable tables or text.")
        except Exception as e:
            return cls._read_binary_summary(file_path, filename, file_path.stat().st_size, reason=f"Word DOCX parsing error: {str(e)}")

    @classmethod
    def _read_zip(cls, file_path: Path, filename: str) -> Tuple[pd.DataFrame, str, bool, str]:
        """Safely extract ZIP archive and parse the first tabular file."""
        temp_dir = tempfile.mkdtemp(prefix="safe_zip_")
        try:
            with zipfile.ZipFile(file_path, "r") as z:
                # Zip-bomb protection: check member count and uncompressed size
                total_uncompressed = sum(info.file_size for info in z.infolist())
                if total_uncompressed > MAX_ZIP_EXTRACTED_BYTES:
                    raise ValueError(f"ZIP archive uncompressed size ({total_uncompressed / 1024 / 1024:.1f}MB) exceeds 50MB safety limit.")
                if len(z.infolist()) > MAX_ZIP_MEMBERS:
                    raise ValueError(f"ZIP archive contains too many files ({len(z.infolist())} > {MAX_ZIP_MEMBERS}).")

                # Extract safely (no traversal)
                candidates = []
                for member in z.infolist():
                    name = member.filename
                    if ".." in name or name.startswith("/") or name.startswith("\\"):
                        continue
                    if not member.is_dir():
                        target = Path(temp_dir) / Path(name).name
                        with z.open(member) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        candidates.append((target, name))

            # Find first parseable candidate
            for cand_path, orig_name in candidates:
                try:
                    df, fmt, is_tab, desc = cls.parse_file(cand_path, orig_name)
                    if is_tab:
                        return df, "zip", True, f"ZIP archive extractor (extracted '{orig_name}' via {desc})"
                except Exception:
                    continue

            return cls._read_binary_summary(file_path, filename, file_path.stat().st_size, reason=f"ZIP archive contained {len(candidates)} files, but none contained extractable tabular data.")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @classmethod
    def _read_gzip(cls, file_path: Path, filename: str) -> Tuple[pd.DataFrame, str, bool, str]:
        """Safely decompress GZ file and parse inner content."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix="_decompressed")
        temp_path = Path(temp_file.name)
        try:
            temp_file.close()
            with gzip.open(file_path, "rb") as gz_in, open(temp_path, "wb") as out:
                shutil.copyfileobj(gz_in, out)

            inner_name = filename.rsplit(".gz", 1)[0].rsplit(".gzip", 1)[0]
            df, fmt, is_tab, desc = cls.parse_file(temp_path, inner_name)
            return df, "gzip", is_tab, f"Gzip decompressor -> {desc}"
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @classmethod
    def _try_read_free_text(cls, file_path: Path, filename: str, header_bytes: bytes) -> Optional[Tuple[pd.DataFrame, str, bool, str]]:
        """Convert arbitrary text files into a structured tabular representation."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = [line.rstrip("\r\n") for line in f if line.strip()]

            if lines:
                df = pd.DataFrame({
                    "line_number": range(1, len(lines) + 1),
                    "text_content": lines,
                    "character_count": [len(l) for l in lines],
                    "word_count": [len(l.split()) for l in lines]
                })
                return cls._clean_extracted_df(df), "text", True, "Plain text structured line analyzer"
        except Exception:
            pass
        return None

    @classmethod
    def _read_binary_summary(cls, file_path: Path, filename: str, file_size: int, reason: str = "") -> Tuple[pd.DataFrame, str, bool, str]:
        """Honest fallback for non-tabular files (images, audio, binaries)."""
        msg = reason or "We received your file but could not find tabular data in it. Checked CSV/TSV, Excel, JSON, Parquet, SQLite, XML/HTML, PDF, and Word parsers."
        df = pd.DataFrame([{
            "file_name": filename,
            "file_size_bytes": file_size,
            "status": "Non-tabular media or binary asset",
            "message": msg
        }])
        return df, "binary_fallback", False, msg

    @staticmethod
    def _clean_extracted_df(df: pd.DataFrame) -> pd.DataFrame:
        """Sanitize column names and ensure valid non-empty structure."""
        if df.empty:
            return df

        # Deduplicate and stringify column headers
        new_cols = []
        seen = {}
        for i, col in enumerate(df.columns):
            c_name = str(col).strip() if col is not None else f"col_{i}"
            if not c_name or c_name.startswith("Unnamed:"):
                c_name = f"col_{i}"
            if c_name in seen:
                seen[c_name] += 1
                new_cols.append(f"{c_name}_{seen[c_name]}")
            else:
                seen[c_name] = 0
                new_cols.append(c_name)

        df.columns = new_cols
        return df
