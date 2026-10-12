"""Interactive Analytics Dashboard page for Autonomous AI Data Analyst Agent.
Neo-morphism 60% + Minimalism 40% design with ranked findings, Recharts visualizations,
executive summary, citation verification, and human-in-the-loop feedback.
"""
from typing import Any, Dict
import reflex as rx
from frontend.components.layout import app_layout
from frontend.components.neu_components import (
    citation_chip,
    empty_state,
    neu_button,
    neu_card,
    neu_inset_card,
    progress_track,
    status_pill,
)
from frontend.state import AppState, InsightModel, RunLogStepModel
from frontend.theme import (
    ACCENT_COLOR,
    ACCENT_HOVER,
    ACCENT_SUBTLE,
    FONT_SERIF,
    RADIUS_FULL,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    RADIUS_XL,
    SHADOW_INSET,
    SHADOW_INSET_DEEP,
    SHADOW_RAISED,
    SHADOW_RAISED_SM,
    SURFACE_COLOR,
    TEXT_COLOR,
    TEXT_MUTED,
)


def kpi_card(title: str, value: Any, subtitle: str, icon: str, status: str = "info") -> rx.Component:
    """Minimalist Neumorphic KPI stat card."""
    color_map = {
        "success": "var(--status-success)",
        "warn": "var(--status-warning)",
        "error": "var(--status-error)",
        "info": ACCENT_COLOR,
    }
    icon_color = color_map.get(status, ACCENT_COLOR)

    return neu_card(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon(tag=icon, size=16, color=icon_color),
                    padding="0.5rem",
                    border_radius=RADIUS_FULL,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_INSET,
                ),
                rx.spacer(),
                rx.text(title, font_size="0.75rem", font_weight="500", color=TEXT_MUTED),
                width="100%",
                align_items="center",
            ),
            rx.text(
                value,
                font_size="1.45rem",
                font_weight="700",
                color=TEXT_COLOR,
                letter_spacing="-0.02em",
                class_name="tabular-nums",
            ),
            rx.text(
                subtitle,
                font_size="0.72rem",
                color=TEXT_MUTED,
            ),
            spacing="1",
            align_items="flex-start",
            width="100%",
        ),
        sm=True,
        width="100%",
    )


def render_insight_chart(ins: InsightModel) -> rx.Component:
    """Render recharts visualization from embedded insight chart_spec with muted slate-teal and pastel accents."""
    return rx.cond(
        ins.chart_spec,
        rx.box(
            rx.vstack(
                rx.text(
                    ins.chart_spec.title,
                    font_size="0.78rem",
                    font_weight="600",
                    color=TEXT_COLOR,
                ),
                rx.cond(
                    ins.chart_spec.chart_type == "line",
                    rx.recharts.line_chart(
                        rx.recharts.line(
                            data_key=ins.chart_spec.y_key,
                            stroke=ACCENT_COLOR,
                            stroke_width=2,
                            dot={"r": 3, "fill": ACCENT_COLOR},
                        ),
                        rx.recharts.x_axis(data_key=ins.chart_spec.x_key, stroke=TEXT_MUTED, font_size="0.7rem"),
                        rx.recharts.y_axis(stroke=TEXT_MUTED, font_size="0.7rem"),
                        rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="var(--border-subtle)"),
                        rx.recharts.graphing_tooltip(),
                        data=ins.chart_spec.data,
                        height=180,
                        width="100%",
                    ),
                    rx.cond(
                        ins.chart_spec.chart_type == "scatter",
                        rx.recharts.scatter_chart(
                            rx.recharts.scatter(data_key=ins.chart_spec.y_key, fill=ACCENT_COLOR),
                            rx.recharts.x_axis(data_key=ins.chart_spec.x_key, stroke=TEXT_MUTED, font_size="0.7rem"),
                            rx.recharts.y_axis(stroke=TEXT_MUTED, font_size="0.7rem"),
                            rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="var(--border-subtle)"),
                            rx.recharts.graphing_tooltip(),
                            data=ins.chart_spec.data,
                            height=180,
                            width="100%",
                        ),
                        rx.recharts.bar_chart(
                            rx.recharts.bar(data_key=ins.chart_spec.y_key, fill=ACCENT_COLOR, radius=[4, 4, 0, 0]),
                            rx.recharts.x_axis(data_key=ins.chart_spec.x_key, stroke=TEXT_MUTED, font_size="0.7rem"),
                            rx.recharts.y_axis(stroke=TEXT_MUTED, font_size="0.7rem"),
                            rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="var(--border-subtle)"),
                            rx.recharts.graphing_tooltip(),
                            data=ins.chart_spec.data,
                            height=180,
                            width="100%",
                        ),
                    ),
                ),
                spacing="2",
                width="100%",
            ),
            class_name="neu-chart-container",
            padding="0.85rem",
            background_color=SURFACE_COLOR,
            box_shadow=SHADOW_INSET,
            border_radius=RADIUS_MD,
            margin_top="0.65rem",
            width="100%",
        ),
    )


def render_insight_card(ins: InsightModel) -> rx.Component:
    """Render a single ranked insight card with confidence badge, metrics, caveats, and feedback."""
    confidence_badge = rx.cond(
        ins.confidence == "high",
        rx.box(
            rx.text("HIGH CONFIDENCE", font_size="0.68rem", font_weight="700", color="var(--status-success)"),
            padding="0.15rem 0.45rem",
            border_radius=RADIUS_SM,
            background_color=SURFACE_COLOR,
            box_shadow=SHADOW_INSET,
        ),
        rx.cond(
            ins.confidence == "medium",
            rx.box(
                rx.text("MEDIUM CONFIDENCE", font_size="0.68rem", font_weight="700", color="var(--status-warning)"),
                padding="0.15rem 0.45rem",
                border_radius=RADIUS_SM,
                background_color=SURFACE_COLOR,
                box_shadow=SHADOW_INSET,
            ),
            rx.box(
                rx.text("LOW CONFIDENCE", font_size="0.68rem", font_weight="700", color="var(--status-error)"),
                padding="0.15rem 0.45rem",
                border_radius=RADIUS_SM,
                background_color=SURFACE_COLOR,
                box_shadow=SHADOW_INSET,
            ),
        ),
    )

    return neu_card(
        rx.vstack(
            # Top row: Type badge, confidence, impact score
            rx.hstack(
                rx.box(
                    rx.text(ins.type, font_size="0.7rem", font_weight="600", color=ACCENT_COLOR),
                    padding="0.15rem 0.5rem",
                    border_radius=RADIUS_SM,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_RAISED_SM,
                ),
                confidence_badge,
                rx.spacer(),
                rx.box(
                    rx.text(f"Impact: {ins.impact_score:.2f}", font_size="0.7rem", color=TEXT_MUTED, font_weight="500"),
                    padding="0.15rem 0.45rem",
                    border_radius=RADIUS_SM,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_INSET,
                ),
                width="100%",
                align_items="center",
            ),

            # Title
            rx.text(ins.title, font_weight="600", font_size="0.95rem", color=TEXT_COLOR, line_height="1.3"),

            # Narrative Summary
            rx.text(ins.summary, font_size="0.825rem", color=TEXT_MUTED, line_height="1.5"),

            # Coverage & Exclusion stats
            rx.hstack(
                rx.box(
                    rx.text(f"Used: {ins.n_used} rows", font_size="0.7rem", color=TEXT_MUTED),
                    padding="0.15rem 0.45rem",
                    border_radius=RADIUS_SM,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_INSET,
                ),
                rx.box(
                    rx.text(f"Excluded: {ins.n_excluded} rows", font_size="0.7rem", color=TEXT_MUTED),
                    padding="0.15rem 0.45rem",
                    border_radius=RADIUS_SM,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_INSET,
                ),
                rx.box(
                    rx.text(f"Exclusion: {ins.exclusion_rate * 100:.1f}%", font_size="0.7rem", color="var(--status-warning)"),
                    padding="0.15rem 0.45rem",
                    border_radius=RADIUS_SM,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_INSET,
                ),
                spacing="2",
                align_items="center",
                wrap="wrap",
            ),

            # Caveats
            rx.cond(
                ins.caveats.length() > 0,
                neu_inset_card(
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="triangle-alert", size=12, color="var(--status-warning)"),
                            rx.text("Caveats & Limitations:", font_size="0.72rem", font_weight="600", color="var(--status-warning)"),
                            spacing="1",
                            align_items="center",
                        ),
                        rx.foreach(
                            ins.caveats,
                            lambda c: rx.text(f"• {c}", font_size="0.75rem", color=TEXT_MUTED),
                        ),
                        spacing="1",
                        align_items="flex-start",
                        width="100%",
                    ),
                    padding="0.6rem 0.85rem",
                    width="100%",
                ),
            ),

            # Embedded visualization
            render_insight_chart(ins),

            # Human-in-the-Loop Feedback Row (Plan §8.6)
            rx.hstack(
                rx.text("Was this insight helpful?", font_size="0.72rem", color=TEXT_MUTED),
                rx.spacer(),
                rx.button(
                    rx.hstack(
                        rx.icon(tag="thumbs-up", size=12),
                        rx.text("Helpful", font_size="0.72rem"),
                        spacing="1",
                        align_items="center",
                    ),
                    on_click=AppState.submit_insight_feedback(ins.id, "helpful"),
                    background_color=SURFACE_COLOR,
                    box_shadow=rx.cond(
                        AppState.insight_feedback_map[ins.id] == "helpful",
                        SHADOW_INSET,
                        SHADOW_RAISED_SM,
                    ),
                    color=rx.cond(
                        AppState.insight_feedback_map[ins.id] == "helpful",
                        "var(--status-success)",
                        TEXT_MUTED,
                    ),
                    border="none",
                    border_radius=RADIUS_SM,
                    padding="0.3rem 0.65rem",
                    cursor="pointer",
                    transition="all 150ms ease",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon(tag="thumbs-down", size=12),
                        rx.text("Not Relevant", font_size="0.72rem"),
                        spacing="1",
                        align_items="center",
                    ),
                    on_click=AppState.submit_insight_feedback(ins.id, "not_relevant"),
                    background_color=SURFACE_COLOR,
                    box_shadow=rx.cond(
                        AppState.insight_feedback_map[ins.id] == "not_relevant",
                        SHADOW_INSET,
                        SHADOW_RAISED_SM,
                    ),
                    color=rx.cond(
                        AppState.insight_feedback_map[ins.id] == "not_relevant",
                        "var(--status-error)",
                        TEXT_MUTED,
                    ),
                    border="none",
                    border_radius=RADIUS_SM,
                    padding="0.3rem 0.65rem",
                    cursor="pointer",
                    transition="all 150ms ease",
                ),
                spacing="2",
                align_items="center",
                width="100%",
                margin_top="0.4rem",
            ),

            spacing="3",
            align_items="flex-start",
            width="100%",
        ),
        width="100%",
    )


def executive_summary_panel() -> rx.Component:
    """Render executive summary narrative with verified citation badge and strategic recommendations."""
    return neu_card(
        rx.vstack(
            rx.hstack(
                rx.hstack(
                    rx.icon(tag="sparkles", size=18, color=ACCENT_COLOR),
                    rx.text("Executive Narrative Summary", font_size="1.05rem", font_weight="600", color=TEXT_COLOR),
                    spacing="2",
                    align_items="center",
                ),
                rx.spacer(),
                # Verified citations status pill
                status_pill(
                    AppState.verification_badge_text,
                    icon="shield-check",
                    status=rx.cond(AppState.verification_is_valid, "success", "warn"),
                ),
                width="100%",
                align_items="center",
            ),

            # Narrative body
            rx.text(
                AppState.job_executive_summary,
                font_size="0.875rem",
                color=TEXT_COLOR,
                line_height="1.6",
            ),

            # Strategic Recommendations
            rx.cond(
                AppState.job_recommendations.length() > 0,
                neu_inset_card(
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="compass", size=14, color=ACCENT_COLOR),
                            rx.text("Strategic Recommendations", font_size="0.825rem", font_weight="600", color=TEXT_COLOR),
                            spacing="2",
                            align_items="center",
                        ),
                        rx.foreach(
                            AppState.job_recommendations,
                            lambda rec: rx.hstack(
                                rx.icon(tag="check", size=13, color=ACCENT_COLOR),
                                rx.text(rec, font_size="0.8rem", color=TEXT_MUTED, line_height="1.45"),
                                spacing="2",
                                align_items="flex-start",
                            ),
                        ),
                        spacing="2",
                        align_items="flex-start",
                        width="100%",
                    ),
                    padding="0.85rem 1rem",
                    width="100%",
                ),
            ),

            spacing="3",
            align_items="flex-start",
            width="100%",
        ),
        width="100%",
    )


def data_quality_panel() -> rx.Component:
    """Render sanitization audit: sentinels, domain invalid values, returns kept, and imputation."""
    return neu_card(
        rx.vstack(
            rx.hstack(
                rx.hstack(
                    rx.icon(tag="shield-alert", size=18, color=ACCENT_COLOR),
                    rx.text("Data Quality & Cleaning Audit", font_size="1rem", font_weight="600", color=TEXT_COLOR),
                    spacing="2",
                    align_items="center",
                ),
                rx.spacer(),
                status_pill(AppState.quality_score_text, icon="award", status="info"),
                width="100%",
                align_items="center",
            ),

            # 3-column cards
            rx.grid(
                neu_inset_card(
                    rx.vstack(
                        rx.text("Sentinels Sanitized", font_size="0.75rem", font_weight="600", color=TEXT_MUTED),
                        rx.cond(
                            AppState.sentinels_list.length() > 0,
                            rx.foreach(
                                AppState.sentinels_list,
                                lambda s: rx.hstack(
                                    rx.text(s["column"].to_string(), font_size="0.75rem", font_weight="600", color=TEXT_COLOR),
                                    rx.text(f"val: {s['value'].to_string()} ({s['count'].to_string()} rows)", font_size="0.7rem", color=TEXT_MUTED),
                                    spacing="1",
                                ),
                            ),
                            rx.text("None detected", font_size="0.75rem", color=TEXT_MUTED, font_style="italic"),
                        ),
                        spacing="1",
                        align_items="flex-start",
                        width="100%",
                    ),
                    padding="0.75rem 0.9rem",
                ),
                neu_inset_card(
                    rx.vstack(
                        rx.text("Domain Invalids Sanitized", font_size="0.75rem", font_weight="600", color=TEXT_MUTED),
                        rx.cond(
                            AppState.invalid_values_list.length() > 0,
                            rx.foreach(
                                AppState.invalid_values_list,
                                lambda iv: rx.hstack(
                                    rx.text(iv["column"].to_string(), font_size="0.75rem", font_weight="600", color=TEXT_COLOR),
                                    rx.text(f"{iv['rule'].to_string()} ({iv['count'].to_string()} rows)", font_size="0.7rem", color=TEXT_MUTED),
                                    spacing="1",
                                ),
                            ),
                            rx.text("None detected", font_size="0.75rem", color=TEXT_MUTED, font_style="italic"),
                        ),
                        spacing="1",
                        align_items="flex-start",
                        width="100%",
                    ),
                    padding="0.75rem 0.9rem",
                ),
                neu_inset_card(
                    rx.vstack(
                        rx.text("Suspected Returns (Kept)", font_size="0.75rem", font_weight="600", color=TEXT_MUTED),
                        rx.cond(
                            AppState.suspected_returns_list.length() > 0,
                            rx.foreach(
                                AppState.suspected_returns_list,
                                lambda sr: rx.hstack(
                                    rx.text(sr["column"].to_string(), font_size="0.75rem", font_weight="600", color=TEXT_COLOR),
                                    rx.text(f"{sr['count'].to_string()} records kept", font_size="0.7rem", color=TEXT_MUTED),
                                    spacing="1",
                                ),
                            ),
                            rx.text("None detected", font_size="0.75rem", color=TEXT_MUTED, font_style="italic"),
                        ),
                        spacing="1",
                        align_items="flex-start",
                        width="100%",
                    ),
                    padding="0.75rem 0.9rem",
                ),
                columns=rx.breakpoints(initial="1", sm="3"),
                spacing="3",
                width="100%",
            ),

            # Imputation table
            rx.cond(
                AppState.imputation_stats_list.length() > 0,
                rx.vstack(
                    rx.text("Column Imputation Rates & Missing Value Strategies", font_size="0.8rem", font_weight="600", color=TEXT_COLOR),
                    rx.box(
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Column"),
                                    rx.table.column_header_cell("Imputed Rows"),
                                    rx.table.column_header_cell("Rate"),
                                    rx.table.column_header_cell("Strategy"),
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    AppState.imputation_stats_list,
                                    lambda imp: rx.table.row(
                                        rx.table.cell(rx.text(imp["column"].to_string(), font_size="0.78rem", font_weight="600", color=TEXT_COLOR)),
                                        rx.table.cell(rx.text(imp["count"].to_string(), font_size="0.75rem", color=TEXT_MUTED)),
                                        rx.table.cell(rx.text(imp["rate"].to_string(), font_size="0.75rem", color="var(--status-warning)")),
                                        rx.table.cell(rx.text(imp["strategy"].to_string(), font_size="0.75rem", color=TEXT_MUTED)),
                                    )
                                )
                            ),
                            width="100%",
                        ),
                        background_color=SURFACE_COLOR,
                        box_shadow=SHADOW_INSET,
                        border_radius=RADIUS_MD,
                        padding="0.5rem",
                        width="100%",
                        overflow_x="auto",
                    ),
                    spacing="2",
                    width="100%",
                    margin_top="0.5rem",
                ),
            ),

            spacing="3",
            align_items="flex-start",
            width="100%",
        ),
        width="100%",
    )


def dashboard_page() -> rx.Component:
    """Dashboard page combining KPIs, execution status, ranked findings, narrative, and sanitization."""
    return app_layout(
        "Dashboard",
        rx.vstack(
            # 1. Top KPI metrics
            rx.grid(
                kpi_card("Dataset Quality", AppState.quality_score_text, "Composite benchmark", "award", "success"),
                kpi_card("Analyzed Rows", AppState.row_count, "Clean records", "layers", "info"),
                kpi_card("Ranked Insights", AppState.job_insights.length(), "Validated findings", "sparkles", "info"),
                kpi_card("Grounding Audit", AppState.verification_rate_text, "Verified citations", "shield-check", "success"),
                columns=rx.breakpoints(initial="1", sm="2", lg="4"),
                spacing="3",
                width="100%",
            ),

            # 2. If job is actively running, show quick monitor card linking to /run
            rx.cond(
                AppState.job_status == "running",
                neu_card(
                    rx.hstack(
                        rx.box(
                            width="10px",
                            height="10px",
                            border_radius=RADIUS_FULL,
                            background_color=ACCENT_COLOR,
                            class_name="neu-active-step-pulse",
                        ),
                        rx.vstack(
                            rx.text("Autonomous Agent In Flight", font_size="0.9rem", font_weight="600", color=TEXT_COLOR),
                            rx.text(
                                AppState.running_status_text,
                                font_size="0.8rem",
                                color=TEXT_MUTED,
                            ),
                            spacing="0",
                            align_items="flex-start",
                        ),
                        rx.spacer(),
                        rx.link(
                            neu_button(
                                rx.hstack(
                                    rx.icon(tag="activity", size=14),
                                    rx.text("View Run Monitor"),
                                    spacing="1",
                                    align_items="center",
                                ),
                                variant="primary",
                            ),
                            href="/run",
                            text_decoration="none",
                        ),
                        spacing="3",
                        align_items="center",
                        width="100%",
                    ),
                    width="100%",
                ),
            ),

            # 3. Main Results (When results are populated)
            rx.cond(
                AppState.job_insights.length() > 0,
                rx.vstack(
                    # Executive Narrative
                    executive_summary_panel(),

                    # Top Analytical Insights Section
                    neu_card(
                        rx.vstack(
                            rx.hstack(
                                rx.hstack(
                                    rx.icon(tag="sparkles", size=18, color=ACCENT_COLOR),
                                    rx.text("Top Ranked Analytical Insights", font_size="1.05rem", font_weight="600", color=TEXT_COLOR),
                                    spacing="2",
                                    align_items="center",
                                ),
                                rx.spacer(),
                                status_pill("Ranked by Effect & Significance", icon="trending-up", status="info"),
                                width="100%",
                                align_items="center",
                            ),
                            rx.text(
                                "Core statistical findings scored by effect size (Cohen's d), p-value significance, and sample coverage.",
                                font_size="0.825rem",
                                color=TEXT_MUTED,
                            ),
                            rx.grid(
                                rx.foreach(AppState.job_analytical_insights, render_insight_card),
                                columns=rx.breakpoints(initial="1", md="2"),
                                spacing="3",
                                width="100%",
                            ),
                            spacing="3",
                            align_items="flex-start",
                            width="100%",
                        ),
                        width="100%",
                    ),

                    # Data Quality Findings Section
                    rx.cond(
                        AppState.job_data_quality_insights.length() > 0,
                        neu_card(
                            rx.vstack(
                                rx.hstack(
                                    rx.hstack(
                                        rx.icon(tag="shield-alert", size=18, color="var(--status-warning)"),
                                        rx.text("Data Quality & Sanitization Caveats", font_size="1.05rem", font_weight="600", color=TEXT_COLOR),
                                        spacing="2",
                                        align_items="center",
                                    ),
                                    rx.spacer(),
                                    status_pill("Audit Caveats", icon="triangle-alert", status="warn"),
                                    width="100%",
                                    align_items="center",
                                ),
                                rx.text(
                                    "Sanitized sentinels, domain invalid values, elevated imputation rates, and small-sample caveats.",
                                    font_size="0.825rem",
                                    color=TEXT_MUTED,
                                ),
                                rx.grid(
                                    rx.foreach(AppState.job_data_quality_insights, render_insight_card),
                                    columns=rx.breakpoints(initial="1", md="2"),
                                    spacing="3",
                                    width="100%",
                                ),
                                spacing="3",
                                align_items="flex-start",
                                width="100%",
                            ),
                            width="100%",
                        ),
                    ),

                    # Data Quality & Cleaning Audit Panel
                    data_quality_panel(),

                    spacing="4",
                    width="100%",
                ),
                # Honest Empty State when no results exist
                rx.cond(
                    AppState.job_status != "running",
                    empty_state(
                        title="No Analysis Results Ready",
                        description="Select or upload a dataset, formulate an analysis goal, and launch an autonomous agent job to populate ranked insights, charts, and executive narrative.",
                        icon="layout-dashboard",
                        action_button=rx.link(
                            neu_button(
                                rx.hstack(
                                    rx.icon(tag="upload", size=14),
                                    rx.text("Go to Datasets & Upload"),
                                    spacing="2",
                                    align_items="center",
                                ),
                                variant="primary",
                            ),
                            href="/upload",
                            text_decoration="none",
                        ),
                    ),
                ),
            ),

            spacing="4",
            width="100%",
        ),
    )
