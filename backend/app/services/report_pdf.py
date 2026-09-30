"""Production-grade PDF Report Generation Engine via ReportLab (Milestone 5).

Generates complete, publication-ready data analysis reports:
1. Cover page: Document title, dataset metadata, generation timestamp, and LLM provider/model.
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

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.app.services.chart_render import render_chart_to_png

# Palette
C_PRIMARY = colors.HexColor("#4f46e5")
C_DARK = colors.HexColor("#0f172a")
C_TEXT = colors.HexColor("#1e293b")
C_MUTED = colors.HexColor("#64748b")
C_LIGHT_BG = colors.HexColor("#f8fafc")
C_BORDER = colors.HexColor("#cbd5e1")
C_GREEN = colors.HexColor("#10b981")
C_AMBER = colors.HexColor("#f59e0b")
C_RED = colors.HexColor("#ef4444")

def build_pdf_styles():
    """Create distinct, modern typography styles."""
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name="ReportCoverTitle",
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=C_PRIMARY,
        spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        name="ReportCoverSubtitle",
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=C_MUTED,
        spaceAfter=25
    ))
    styles.add(ParagraphStyle(
        name="ReportH1",
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=C_DARK,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name="ReportH2",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=C_PRIMARY,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name="ReportBody",
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=C_TEXT,
        spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name="ReportCaveat",
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12,
        textColor=C_AMBER,
        spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name="TableHead",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=0
    ))
    styles.add(ParagraphStyle(
        name="TableCell",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=C_TEXT,
        alignment=0
    ))
    styles.add(ParagraphStyle(
        name="TableCellBold",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=C_DARK,
        alignment=0
    ))
    return styles

def generate_pdf_report(
    output_path: Union[str, Path],
    dataset_name: str,
    job_data: Dict[str, Any],
    profile_data: Optional[Dict[str, Any]] = None,
    cleaning_data: Optional[Dict[str, Any]] = None,
    provider: str = "Gemini",
    model_name: str = "gemini-2.5-flash"
) -> Path:
    """Generate complete PDF report at output_path."""
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    
    doc = SimpleDocTemplate(
        str(out_p),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = build_pdf_styles()
    story = []
    
    # ---------------------------------------------------------
    # 1. COVER / HEADER BLOCK
    # ---------------------------------------------------------
    story.append(Paragraph("Autonomous AI Data Analyst Report", styles["ReportCoverTitle"]))
    gen_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    story.append(Paragraph(f"Dataset: <b>{dataset_name}</b> | Generated: {gen_time} | Orchestrator: {provider} ({model_name})", styles["ReportCoverSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C_PRIMARY, spaceAfter=15))
    
    # Overview meta table
    results = job_data.get("results") or {}
    synthesis = results.get("synthesis") or {}
    insights = results.get("insights") or []
    run_log = job_data.get("run_log") or []
    verification = job_data.get("verification") or {}
    
    q_score = (profile_data or {}).get("quality_summary", {}).get("quality_score", 100.0)
    row_cnt = (profile_data or {}).get("row_count", 0)
    col_cnt = (profile_data or {}).get("column_count", 0)
    
    meta_table_data = [
        [
            Paragraph(f"<b>Clean Records:</b> {row_cnt:,}", styles["TableCell"]),
            Paragraph(f"<b>Dimensions:</b> {col_cnt} attributes", styles["TableCell"]),
            Paragraph(f"<b>Quality Score:</b> {q_score}/100", styles["TableCell"]),
            Paragraph(f"<b>Insights Generated:</b> {len(insights)}", styles["TableCell"])
        ]
    ]
    t_meta = Table(meta_table_data, colWidths=[130, 130, 130, 140])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C_LIGHT_BG),
        ('BOX', (0,0), (-1,-1), 1, C_BORDER),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 15))
    
    # ---------------------------------------------------------
    # 2. EXECUTIVE SUMMARY & CITATION AUDIT
    # ---------------------------------------------------------
    story.append(Paragraph("1. Executive Summary", styles["ReportH1"]))
    exec_summary = synthesis.get("executive_summary") or "Comprehensive automated analysis completed across all dimensions."
    story.append(Paragraph(exec_summary, styles["ReportBody"]))
    
    # Citation Badge Block
    v_rate = verification.get("verification_rate_percent", 100.0)
    v_checked = verification.get("total_claims_checked", 0)
    v_valid = verification.get("is_valid", True)
    ver_status_color = C_GREEN if v_valid else C_AMBER
    ver_box = [
        [Paragraph(f"<b>Citation Grounding Audit:</b> {v_rate}% verified ({verification.get('verified_claims_count', 0)}/{v_checked} claims).", styles["TableCellBold"])]
    ]
    t_ver = Table(ver_box, colWidths=[530])
    t_ver.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f0fdf4") if v_valid else colors.HexColor("#fffbeb")),
        ('BOX', (0,0), (-1,-1), 1, ver_status_color),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_ver)
    story.append(Spacer(1, 10))
    
    # Recommendations
    recs = synthesis.get("recommendations", [])
    if recs:
        story.append(Paragraph("Strategic Recommendations:", styles["ReportH2"]))
        for r in recs:
            story.append(Paragraph(f"• {r}", styles["ReportBody"]))
    story.append(Spacer(1, 15))
    
    # ---------------------------------------------------------
    # 3. TOP RANKED INSIGHTS WITH CHARTS
    # ---------------------------------------------------------
    story.append(Paragraph("2. Top Autonomous Insights & Visualizations", styles["ReportH1"]))
    story.append(Paragraph("Each insight is objectively scored and categorized with full statistical sample bounds and caveats.", styles["ReportBody"]))
    
    # Temporary directory for chart images
    temp_dir = out_p.parent / f"tmp_charts_{out_p.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    chart_files = []
    try:
        for idx, ins in enumerate(insights[:8]):
            ins_story = []
            title = ins.get("title", f"Insight #{idx+1}")
            summary = ins.get("summary", "")
            ins_type = ins.get("type", "insight")
            conf = ins.get("confidence", "high").upper()
            impact = ins.get("impact_score", 0.0)
            n_used = ins.get("n_used", 0)
            n_excl = ins.get("n_excluded", 0)
            excl_rate = round(ins.get("exclusion_rate", 0.0) * 100, 1)
            caveats = ins.get("caveats", [])
            chart_spec = ins.get("chart_spec")
            
            ins_story.append(Paragraph(f"#{idx+1} {title} <font color='#6366f1'>[{ins_type}]</font>", styles["ReportH2"]))
            ins_story.append(Paragraph(summary, styles["ReportBody"]))
            
            # Badge line
            badge_text = f"<b>Confidence:</b> {conf} | <b>Impact Score:</b> {impact:.2f} | <b>Sample:</b> n={n_used} used, {n_excl} excluded ({excl_rate}%)"
            ins_story.append(Paragraph(badge_text, styles["ReportBody"]))
            
            # Caveats
            for c in caveats:
                ins_story.append(Paragraph(f"⚠️ <i>Caveat:</i> {c}", styles["ReportCaveat"]))
                
            # Render chart image if spec exists
            if chart_spec:
                img_path = temp_dir / f"chart_{idx}.png"
                try:
                    render_chart_to_png(chart_spec, output_path=img_path, width_in=6.0, height_in=2.8, dpi=130)
                    chart_files.append(img_path)
                    ins_story.append(Spacer(1, 4))
                    ins_story.append(Image(str(img_path), width=480, height=210))
                except Exception:
                    pass
                    
            ins_story.append(Spacer(1, 12))
            story.append(KeepTogether(ins_story))
    finally:
        pass
        
    story.append(Spacer(1, 15))
    
    # ---------------------------------------------------------
    # 4. DATA QUALITY & CLEANING SECTION
    # ---------------------------------------------------------
    story.append(Paragraph("3. Data Quality & Sanitization Audit", styles["ReportH1"]))
    cl_report = cleaning_data or {}
    
    sentinels = cl_report.get("sentinels_detected", [])
    invalids = cl_report.get("invalid_values_detected", [])
    returns = cl_report.get("suspected_returns", [])
    imputations = cl_report.get("column_imputation_stats", {})
    
    # Sentinels & Invalid Values table
    dq_rows = [["Data Quality Rule", "Column", "Value / Condition", "Rows Affected", "Action Taken"]]
    for s in sentinels:
        dq_rows.append([
            Paragraph("Sentinel Placeholder", styles["TableCellBold"]),
            Paragraph(str(s.get("column")), styles["TableCell"]),
            Paragraph(str(s.get("sentinel_value")), styles["TableCell"]),
            Paragraph(str(s.get("count")), styles["TableCell"]),
            Paragraph("Auto-converted to NaN", styles["TableCell"])
        ])
    for iv in invalids:
        dq_rows.append([
            Paragraph("Domain Rule Violation", styles["TableCellBold"]),
            Paragraph(str(iv.get("column")), styles["TableCell"]),
            Paragraph(str(iv.get("rule")), styles["TableCell"]),
            Paragraph(str(iv.get("count")), styles["TableCell"]),
            Paragraph("Invalidated to NaN", styles["TableCell"])
        ])
    for r in returns:
        dq_rows.append([
            Paragraph("Suspected Returns", styles["TableCellBold"]),
            Paragraph(str(r.get("column")), styles["TableCell"]),
            Paragraph("Negative count/qty", styles["TableCell"]),
            Paragraph(str(r.get("count")), styles["TableCell"]),
            Paragraph("Flagged & Kept in Data", styles["TableCell"])
        ])
        
    if len(dq_rows) > 1:
        t_dq = Table(dq_rows, colWidths=[110, 95, 115, 85, 125])
        t_dq.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), C_PRIMARY),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, C_LIGHT_BG]),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t_dq)
    else:
        story.append(Paragraph("No anomalous sentinels or domain rule violations detected.", styles["ReportBody"]))
    story.append(Spacer(1, 10))
    
    # Imputation Rates table
    if imputations:
        story.append(Paragraph("Column Imputation Rates:", styles["ReportH2"]))
        imp_rows = [["Column", "Imputed Rows", "Imputation Rate", "Strategy"]]
        for col, stat in sorted(imputations.items(), key=lambda x: -x[1].get("imputation_rate", 0)):
            rate = stat.get("imputation_rate", 0)
            if rate > 0:
                imp_rows.append([
                    Paragraph(str(col), styles["TableCellBold"]),
                    Paragraph(str(stat.get("imputed_count", 0)), styles["TableCell"]),
                    Paragraph(f"{rate*100:.1f}%", styles["TableCell"]),
                    Paragraph(str(stat.get("strategy", "median")), styles["TableCell"])
                ])
        if len(imp_rows) > 1:
            t_imp = Table(imp_rows, colWidths=[150, 110, 110, 160])
            t_imp.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), C_DARK),
                ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, C_LIGHT_BG]),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(t_imp)
    story.append(Spacer(1, 15))
    
    # ---------------------------------------------------------
    # 5. METHODOLOGY & AUDIT TRAIL
    # ---------------------------------------------------------
    story.append(Paragraph("4. Methodology & Execution Audit Trail", styles["ReportH1"]))
    story.append(Paragraph("Full transparent execution trace recording tool invocations, model reasoning, latencies, and token expenditures.", styles["ReportBody"]))
    
    if run_log:
        log_rows = [["Step", "Tool Called", "Model Rationale", "Tool Time", "LLM Latency", "Tokens"]]
        for step in run_log:
            log_rows.append([
                Paragraph(f"#{step.get('step')}", styles["TableCellBold"]),
                Paragraph(str(step.get("tool")), styles["TableCellBold"]),
                Paragraph(str(step.get("rationale", "")), styles["TableCell"]),
                Paragraph(f"{step.get('tool_time_ms', 0):.0f}ms", styles["TableCell"]),
                Paragraph(f"{step.get('llm_latency_ms', 0):.0f}ms", styles["TableCell"]),
                Paragraph(str(step.get("tokens", 0)), styles["TableCell"])
            ])
        t_log = Table(log_rows, colWidths=[35, 95, 230, 55, 65, 50])
        t_log.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), C_DARK),
            ('GRID', (0,0), (-1,-1), 0.5, C_BORDER),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, C_LIGHT_BG]),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t_log)
    story.append(Spacer(1, 15))
    
    # Build Document
    doc.build(story)
    
    # Clean up temporary chart images
    for cf in chart_files:
        try:
            if cf.exists():
                cf.unlink()
        except Exception:
            pass
    try:
        if temp_dir.exists():
            temp_dir.rmdir()
    except Exception:
        pass
        
    return out_p
