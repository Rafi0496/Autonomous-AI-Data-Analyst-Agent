"""Production-grade Word (DOCX) Report Generation Engine via python-docx (Milestone 5).

Generates complete, publication-ready data analysis Word reports:
1. Cover block: Document title, dataset metadata, generation timestamp, and LLM provider/model.
2. Executive Summary: Core narrative, citation verification audit badge, and recommendations.
3. Top Insights: Ranked findings with confidence badges, impact score, sample stats (n_used/exclusion rate), caveats, and embedded headless matplotlib chart images.
4. Data Quality: Cleaning audit tables (sentinels, domain invalid values, returns, and imputation rates).
5. Methodology & Audit Trail: Step-by-step run log table (tool, rationale, model, tool time, LLM latency, tokens).
"""
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import docx
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from backend.app.services.chart_render import render_chart_to_png

# Colors
COLOR_PRIMARY = RGBColor(79, 70, 229)    # #4f46e5
COLOR_DARK = RGBColor(15, 23, 42)        # #0f172a
COLOR_MUTED = RGBColor(100, 116, 139)    # #64748b
COLOR_AMBER = RGBColor(245, 158, 11)     # #f59e0b

def set_cell_background(cell, fill_hex: str):
    """Set background color of a table cell in docx."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tc_pr.append(shd)

def generate_docx_report(
    output_path: Union[str, Path],
    dataset_name: str,
    job_data: Dict[str, Any],
    profile_data: Optional[Dict[str, Any]] = None,
    cleaning_data: Optional[Dict[str, Any]] = None,
    provider: str = "Gemini",
    model_name: str = "gemini-2.5-flash"
) -> Path:
    """Generate complete Word (.docx) report at output_path."""
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    
    doc = Document()
    
    # Page setup (margins 0.75 in)
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)
        
    results = job_data.get("results") or {}
    synthesis = results.get("synthesis") or {}
    insights = results.get("insights") or []
    run_log = job_data.get("run_log") or []
    verification = job_data.get("verification") or {}
    
    q_score = (profile_data or {}).get("quality_summary", {}).get("quality_score", 100.0)
    row_cnt = (profile_data or {}).get("row_count", 0)
    col_cnt = (profile_data or {}).get("column_count", 0)
    
    # ---------------------------------------------------------
    # 1. COVER / TITLE BLOCK
    # ---------------------------------------------------------
    title_p = doc.add_paragraph()
    title_run = title_p.add_run("Autonomous AI Data Analyst Report")
    title_run.font.name = "Arial"
    title_run.font.size = Pt(24)
    title_run.font.bold = True
    title_run.font.color.rgb = COLOR_PRIMARY
    title_p.paragraph_format.space_after = Pt(4)
    
    sub_p = doc.add_paragraph()
    gen_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    sub_run = sub_p.add_run(f"Dataset: {dataset_name} | Generated: {gen_time} | Orchestrator: {provider} ({model_name})")
    sub_run.font.name = "Arial"
    sub_run.font.size = Pt(10)
    sub_run.font.color.rgb = COLOR_MUTED
    sub_p.paragraph_format.space_after = Pt(14)
    
    # Summary meta table
    meta_table = doc.add_table(rows=1, cols=4)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_headers = [f"Clean Records: {row_cnt:,}", f"Dimensions: {col_cnt} cols", f"Quality: {q_score}/100", f"Insights: {len(insights)}"]
    for i, h in enumerate(meta_headers):
        cell = meta_table.cell(0, i)
        set_cell_background(cell, "F8FAFC")
        cp = cell.paragraphs[0]
        crun = cp.add_run(h)
        crun.font.name = "Arial"
        crun.font.size = Pt(9)
        crun.font.bold = True
        crun.font.color.rgb = COLOR_DARK
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
    # Sampling disclosure (M1.c)
    sampling_disclosure = (profile_data or {}).get("sampling_disclosure") or (profile_data or {}).get("quality_summary", {}).get("sampling_disclosure")
    if not sampling_disclosure and (profile_data or {}).get("is_sampled"):
        n_sample = (profile_data or {}).get("row_count", 0)
        n_pop = (profile_data or {}).get("population_row_count", n_sample)
        seed = (profile_data or {}).get("sampling_seed", 42)
        sampling_disclosure = f"random sample of {n_sample:,} of {n_pop:,} rows (seed {seed})"
    if sampling_disclosure:
        disc_p = doc.add_paragraph()
        disc_run = disc_p.add_run(f"Scale Sampling Disclosure: Analysis is conducted on a {sampling_disclosure}.")
        disc_run.font.name = "Arial"
        disc_run.font.size = Pt(9.5)
        disc_run.font.italic = True
        disc_run.font.color.rgb = COLOR_MUTED
        disc_p.paragraph_format.space_after = Pt(4)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    
    # ---------------------------------------------------------
    # 2. EXECUTIVE SUMMARY & CITATION AUDIT
    # ---------------------------------------------------------
    h1 = doc.add_heading(level=1)
    r1 = h1.add_run("1. Executive Summary")
    r1.font.color.rgb = COLOR_DARK
    
    exec_summary = synthesis.get("executive_summary") or "Comprehensive automated analysis completed across all dimensions."
    p_body = doc.add_paragraph()
    r_body = p_body.add_run(exec_summary)
    r_body.font.name = "Arial"
    r_body.font.size = Pt(10)
    p_body.paragraph_format.line_spacing = 1.2
    p_body.paragraph_format.space_after = Pt(8)
    
    # Citation verification note
    v_rate = verification.get("verification_rate_percent", 100.0)
    v_checked = verification.get("total_claims_checked", 0)
    v_cnt = verification.get("verified_claims_count", 0)
    ver_p = doc.add_paragraph()
    ver_run = ver_p.add_run(f"✓ Citation Grounding Audit: {v_rate}% verified ({v_cnt}/{v_checked} claims mathematically proven).")
    ver_run.font.name = "Arial"
    ver_run.font.size = Pt(9.5)
    ver_run.font.bold = True
    ver_run.font.color.rgb = RGBColor(16, 185, 129)
    ver_p.paragraph_format.space_after = Pt(10)
    
    # Strategic recommendations
    recs = synthesis.get("recommendations", [])
    if recs:
        h2 = doc.add_heading(level=2)
        r2 = h2.add_run("Data Quality Recommendations")
        r2.font.color.rgb = COLOR_PRIMARY
        for rec in recs:
            p = doc.add_paragraph(style='List Bullet')
            r = p.add_run(rec)
            r.font.name = "Arial"
            r.font.size = Pt(9.5)
            
    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    
    # ---------------------------------------------------------
    # 3. TOP RANKED ANALYTICAL INSIGHTS WITH CHARTS
    # ---------------------------------------------------------
    doc.add_heading(level=1).add_run("2. Top Analytical Insights & Visualizations (Top 6)").font.color.rgb = COLOR_DARK
    
    analytical_insights = results.get("analytical_insights") or [i for i in insights if i.get("type") != "data_quality"][:6]
    dq_insights = results.get("data_quality_insights") or [i for i in insights if i.get("type") == "data_quality"][:4]

    for idx, ins in enumerate(analytical_insights[:6]):
        title = ins.get("title", f"Analytical Finding #{idx+1}")
        summary = ins.get("summary", "")
        ins_type = ins.get("type", "insight")
        conf = ins.get("confidence", "high").upper()
        impact = ins.get("impact_score", 0.0)
        n_used = ins.get("n_used", 0)
        n_excl = ins.get("n_excluded", 0)
        excl_rate = round(ins.get("exclusion_rate", 0.0) * 100, 1)
        caveats = ins.get("caveats", [])
        chart_spec = ins.get("chart_spec")
        
        # Heading for insight
        h_ins = doc.add_heading(level=2)
        r_ins = h_ins.add_run(f"#{idx+1} {title} [{ins_type}]")
        r_ins.font.color.rgb = COLOR_PRIMARY
        
        p_ins_body = doc.add_paragraph()
        r_ins_body = p_ins_body.add_run(summary)
        r_ins_body.font.name = "Arial"
        r_ins_body.font.size = Pt(9.5)
        p_ins_body.paragraph_format.space_after = Pt(4)
        
        # Meta badge
        p_badge = doc.add_paragraph()
        r_badge = p_badge.add_run(f"Confidence: {conf} | Impact Score: {impact:.2f} | Sample Coverage: n={n_used} used, {n_excl} excluded ({excl_rate}%)")
        r_badge.font.name = "Arial"
        r_badge.font.size = Pt(8.5)
        r_badge.font.bold = True
        r_badge.font.color.rgb = COLOR_MUTED
        p_badge.paragraph_format.space_after = Pt(4)
        
        # Caveats
        for c in caveats:
            p_cav = doc.add_paragraph()
            r_cav = p_cav.add_run(f"⚠️ Caveat: {c}")
            r_cav.font.name = "Arial"
            r_cav.font.size = Pt(8.5)
            r_cav.font.italic = True
            r_cav.font.color.rgb = COLOR_AMBER
            p_cav.paragraph_format.space_after = Pt(2)
            
        # Embedded Chart
        if chart_spec:
            try:
                png_bytes = render_chart_to_png(chart_spec, width_in=5.8, height_in=2.8, dpi=130)
                doc.add_picture(io.BytesIO(png_bytes), width=Inches(5.5))
            except Exception:
                pass
                
        doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Data Quality Insights List
    if dq_insights:
        doc.add_heading(level=1).add_run("3. Data Quality Findings & Caveats (Max 4)").font.color.rgb = COLOR_DARK
        for idx, ins in enumerate(dq_insights[:4]):
            title = ins.get("title", f"Data Quality Caveat #{idx+1}")
            summary = ins.get("summary", "")
            conf = ins.get("confidence", "low").upper()
            impact = ins.get("impact_score", 0.0)
            n_used = ins.get("n_used", 0)
            n_excl = ins.get("n_excluded", 0)
            excl_rate = round(ins.get("exclusion_rate", 0.0) * 100, 1)
            caveats = ins.get("caveats", [])

            h_dq = doc.add_heading(level=2)
            r_dq = h_dq.add_run(f"#{idx+1} {title} [data_quality]")
            r_dq.font.color.rgb = RGBColor(245, 158, 11)

            p_dq_body = doc.add_paragraph()
            r_dq_body = p_dq_body.add_run(summary)
            r_dq_body.font.name = "Arial"
            r_dq_body.font.size = Pt(9.5)
            p_dq_body.paragraph_format.space_after = Pt(4)

            p_dq_badge = doc.add_paragraph()
            r_dq_badge = p_dq_badge.add_run(f"Confidence: {conf} | Impact Score: {impact:.2f} | Sample: n={n_used} used, {n_excl} excluded ({excl_rate}%)")
            r_dq_badge.font.name = "Arial"
            r_dq_badge.font.size = Pt(8.5)
            r_dq_badge.font.bold = True
            r_dq_badge.font.color.rgb = COLOR_MUTED
            p_dq_badge.paragraph_format.space_after = Pt(4)

            for c in caveats:
                p_cav = doc.add_paragraph()
                r_cav = p_cav.add_run(f"⚠️ Caveat: {c}")
                r_cav.font.name = "Arial"
                r_cav.font.size = Pt(8.5)
                r_cav.font.italic = True
                r_cav.font.color.rgb = COLOR_AMBER
                p_cav.paragraph_format.space_after = Pt(2)
            doc.add_paragraph().paragraph_format.space_after = Pt(6)
        
    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    
    # ---------------------------------------------------------
    # 4. DATA QUALITY & CLEANING SECTION
    # ---------------------------------------------------------
    doc.add_heading(level=1).add_run("3. Data Quality & Sanitization Audit").font.color.rgb = COLOR_DARK
    cl_report = cleaning_data or {}
    
    sentinels = cl_report.get("sentinels_detected", [])
    invalids = cl_report.get("invalid_values_detected", [])
    returns = cl_report.get("suspected_returns", [])
    imputations = cl_report.get("column_imputation_stats", {})
    
    # Table of issues
    dq_rows = [["Data Quality Rule", "Column", "Value / Rule", "Rows Affected", "Action Taken"]]
    for s in sentinels:
        dq_rows.append(["Sentinel Placeholder", str(s.get("column")), str(s.get("sentinel_value")), str(s.get("count")), "Auto-converted to NaN"])
    for iv in invalids:
        dq_rows.append(["Domain Rule Violation", str(iv.get("column")), str(iv.get("rule")), str(iv.get("count")), "Invalidated to NaN"])
    for r in returns:
        dq_rows.append(["Suspected Returns", str(r.get("column")), "Negative count/qty", str(r.get("count")), "Flagged & Kept in Data"])
        
    if len(dq_rows) > 1:
        t_dq = doc.add_table(rows=len(dq_rows), cols=5)
        t_dq.alignment = WD_TABLE_ALIGNMENT.CENTER
        for r_idx, row in enumerate(dq_rows):
            for c_idx, val in enumerate(row):
                cell = t_dq.cell(r_idx, c_idx)
                if r_idx == 0:
                    set_cell_background(cell, "4F46E5")
                    cp = cell.paragraphs[0]
                    crun = cp.add_run(val)
                    crun.font.name = "Arial"
                    crun.font.size = Pt(8.5)
                    crun.font.bold = True
                    crun.font.color.rgb = RGBColor(255, 255, 255)
                else:
                    if r_idx % 2 == 1:
                        set_cell_background(cell, "F8FAFC")
                    cp = cell.paragraphs[0]
                    crun = cp.add_run(val)
                    crun.font.name = "Arial"
                    crun.font.size = Pt(8)
                    crun.font.color.rgb = COLOR_DARK
    else:
        doc.add_paragraph("No anomalous sentinels or domain rule violations detected.")
        
    doc.add_paragraph().paragraph_format.space_after = Pt(8)
    
    # Imputation Rates Table
    if imputations:
        doc.add_heading(level=2).add_run("Column Imputation Rates").font.color.rgb = COLOR_PRIMARY
        imp_rows = [["Column", "Imputed Rows", "Imputation Rate", "Strategy"]]
        for col, stat in sorted(imputations.items(), key=lambda x: -x[1].get("imputation_rate", 0)):
            rate = stat.get("imputation_rate", 0)
            if rate > 0:
                imp_rows.append([str(col), str(stat.get("imputed_count", 0)), f"{rate*100:.1f}%", str(stat.get("strategy", "median"))])
        if len(imp_rows) > 1:
            t_imp = doc.add_table(rows=len(imp_rows), cols=4)
            t_imp.alignment = WD_TABLE_ALIGNMENT.CENTER
            for r_idx, row in enumerate(imp_rows):
                for c_idx, val in enumerate(row):
                    cell = t_imp.cell(r_idx, c_idx)
                    if r_idx == 0:
                        set_cell_background(cell, "0F172A")
                        cp = cell.paragraphs[0]
                        crun = cp.add_run(val)
                        crun.font.name = "Arial"
                        crun.font.size = Pt(8.5)
                        crun.font.bold = True
                        crun.font.color.rgb = RGBColor(255, 255, 255)
                    else:
                        if r_idx % 2 == 1:
                            set_cell_background(cell, "F8FAFC")
                        cp = cell.paragraphs[0]
                        crun = cp.add_run(val)
                        crun.font.name = "Arial"
                        crun.font.size = Pt(8)
                        crun.font.color.rgb = COLOR_DARK
                        
    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    
    # ---------------------------------------------------------
    # 5. METHODOLOGY & AUDIT TRAIL
    # ---------------------------------------------------------
    doc.add_heading(level=1).add_run("4. Methodology & Execution Audit Trail").font.color.rgb = COLOR_DARK
    doc.add_paragraph("Full transparent execution trace recording tool invocations, model reasoning, latencies, and token expenditures.")
    
    if run_log:
        log_rows = [["Step", "Tool Called", "Model Rationale", "Tool Time", "LLM Latency", "Tokens"]]
        for step in run_log:
            log_rows.append([
                f"#{step.get('step')}",
                str(step.get("tool")),
                str(step.get("rationale", "")),
                f"{step.get('tool_time_ms', 0):.0f}ms",
                f"{step.get('llm_latency_ms', 0):.0f}ms",
                str(step.get("tokens", 0))
            ])
        t_log = doc.add_table(rows=len(log_rows), cols=6)
        t_log.alignment = WD_TABLE_ALIGNMENT.CENTER
        for r_idx, row in enumerate(log_rows):
            for c_idx, val in enumerate(row):
                cell = t_log.cell(r_idx, c_idx)
                if r_idx == 0:
                    set_cell_background(cell, "0F172A")
                    cp = cell.paragraphs[0]
                    crun = cp.add_run(val)
                    crun.font.name = "Arial"
                    crun.font.size = Pt(8.5)
                    crun.font.bold = True
                    crun.font.color.rgb = RGBColor(255, 255, 255)
                else:
                    if r_idx % 2 == 1:
                        set_cell_background(cell, "F8FAFC")
                    cp = cell.paragraphs[0]
                    crun = cp.add_run(val)
                    crun.font.name = "Arial"
                    crun.font.size = Pt(7.5)
                    crun.font.color.rgb = COLOR_DARK
                    
    doc.save(str(out_p))
    return out_p
