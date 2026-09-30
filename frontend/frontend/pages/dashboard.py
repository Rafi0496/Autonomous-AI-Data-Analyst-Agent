"""Interactive Analytics Dashboard page for Autonomous AI Data Analyst Agent (Milestone 3)."""
import reflex as rx
from frontend.components.layout import app_layout
from frontend.components.stats_card import stat_card
from frontend.state import AppState, InsightModel, RunLogStepModel

def render_insight_chart(ins: InsightModel) -> rx.Component:
    """Render recharts visualization from embedded insight chart_spec."""
    return rx.cond(
        ins.chart_spec,
        rx.box(
            rx.vstack(
                rx.text(ins.chart_spec.title, font_size="0.8rem", font_weight="600", color="#cbd5e1"),
                rx.cond(
                    ins.chart_spec.chart_type == "line",
                    rx.recharts.line_chart(
                        rx.recharts.line(data_key=ins.chart_spec.y_key, stroke="#6366f1", stroke_width=2),
                        rx.recharts.x_axis(data_key=ins.chart_spec.x_key, stroke="#94a3b8", font_size="0.7rem"),
                        rx.recharts.y_axis(stroke="#94a3b8", font_size="0.7rem"),
                        rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="rgba(255,255,255,0.08)"),
                        rx.recharts.graphing_tooltip(),
                        data=ins.chart_spec.data,
                        height=200,
                        width="100%"
                    ),
                    rx.cond(
                        ins.chart_spec.chart_type == "scatter",
                        rx.recharts.scatter_chart(
                            rx.recharts.scatter(data_key=ins.chart_spec.y_key, fill="#818cf8"),
                            rx.recharts.x_axis(data_key=ins.chart_spec.x_key, stroke="#94a3b8", font_size="0.7rem"),
                            rx.recharts.y_axis(stroke="#94a3b8", font_size="0.7rem"),
                            rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="rgba(255,255,255,0.08)"),
                            rx.recharts.graphing_tooltip(),
                            data=ins.chart_spec.data,
                            height=200,
                            width="100%"
                        ),
                        rx.recharts.bar_chart(
                            rx.recharts.bar(data_key=ins.chart_spec.y_key, fill="#6366f1", radius=[4, 4, 0, 0]),
                            rx.recharts.x_axis(data_key=ins.chart_spec.x_key, stroke="#94a3b8", font_size="0.7rem"),
                            rx.recharts.y_axis(stroke="#94a3b8", font_size="0.7rem"),
                            rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="rgba(255,255,255,0.08)"),
                            rx.recharts.graphing_tooltip(),
                            data=ins.chart_spec.data,
                            height=200,
                            width="100%"
                        )
                    )
                ),
                spacing="2",
                width="100%"
            ),
            padding="1rem",
            background_color="rgba(15, 23, 42, 0.4)",
            border_radius="0.5rem",
            border="1px solid rgba(255, 255, 255, 0.05)",
            margin_top="0.75rem",
            width="100%"
        )
    )

def render_insight_card(ins: InsightModel) -> rx.Component:
    """Render a single ranked insight card with confidence badge, metrics, caveats, and chart."""
    return rx.box(
        rx.vstack(
            # Top row: title, type badge, confidence badge, impact score
            rx.hstack(
                rx.vstack(
                    rx.hstack(
                        rx.badge(ins.type, color_scheme="indigo", variant="soft", size="1"),
                        rx.cond(
                            ins.confidence == "high",
                            rx.badge("HIGH CONFIDENCE", color_scheme="green", variant="solid", size="1"),
                            rx.cond(
                                ins.confidence == "medium",
                                rx.badge("MEDIUM CONFIDENCE", color_scheme="amber", variant="solid", size="1"),
                                rx.badge("LOW CONFIDENCE", color_scheme="red", variant="solid", size="1")
                            )
                        ),
                        rx.badge(f"Impact: {ins.impact_score}", color_scheme="purple", variant="surface", size="1"),
                        spacing="2",
                        align_items="center"
                    ),
                    rx.text(ins.title, font_weight="700", font_size="1rem", color="#f8fafc"),
                    spacing="1",
                    align_items="flex-start"
                ),
                rx.spacer(),
                spacing="3",
                align_items="flex-start",
                width="100%"
            ),

            # Narrative Summary
            rx.text(ins.summary, font_size="0.875rem", color="#cbd5e1", line_height="1.5"),

            # Coverage & Exclusion stats
            rx.hstack(
                rx.badge(f"Used: {ins.n_used} rows", variant="outline", color_scheme="gray", size="1"),
                rx.badge(f"Excluded: {ins.n_excluded} rows", variant="outline", color_scheme="gray", size="1"),
                rx.badge(f"Exclusion Rate: {ins.exclusion_rate * 100}%", variant="outline", color_scheme="amber", size="1"),
                spacing="2",
                align_items="center"
            ),

            # Caveats
            rx.cond(
                ins.caveats.length() > 0,
                rx.vstack(
                    rx.text("Caveats & Limitations:", font_size="0.75rem", font_weight="600", color="#fbbf24"),
                    rx.foreach(
                        ins.caveats,
                        lambda c: rx.hstack(
                            rx.icon(tag="triangle-alert", size=12, color="#fbbf24"),
                            rx.text(c, font_size="0.75rem", color="#f1f5f9"),
                            spacing="1",
                            align_items="center"
                        )
                    ),
                    spacing="1",
                    padding="0.5rem 0.75rem",
                    background_color="rgba(245, 158, 11, 0.08)",
                    border_radius="0.375rem",
                    border="1px solid rgba(245, 158, 11, 0.2)",
                    width="100%"
                )
            ),

            # Embedded visualization
            render_insight_chart(ins),

            spacing="3",
            align_items="flex-start",
            width="100%"
        ),
        padding="1.25rem",
        border_radius="0.75rem",
        background_color="rgba(30, 41, 59, 0.4)",
        border="1px solid rgba(255, 255, 255, 0.08)",
        width="100%"
    )

def render_progress_panel() -> rx.Component:
    """Render background progress timeline and execution status during running jobs."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.spinner(size="2", color="#6366f1"),
                rx.vstack(
                    rx.text("Autonomous Agent Executing...", font_weight="700", font_size="1rem", color="#ffffff"),
                    rx.hstack(
                        rx.badge(f"Phase: {AppState.job_phase.upper()}", color_scheme="indigo", variant="solid", size="1"),
                        rx.text(f"Step {AppState.job_current_step} of {AppState.job_total_steps}: {AppState.job_current_step_name}", font_size="0.8rem", color="#94a3b8"),
                        rx.badge(f"{AppState.job_elapsed_seconds}s elapsed", color_scheme="gray", variant="surface", size="1"),
                        spacing="2",
                        align_items="center"
                    ),
                    spacing="1",
                    align_items="flex-start"
                ),
                rx.spacer(),
                spacing="3",
                align_items="center",
                width="100%"
            ),
            rx.progress(
                value=AppState.job_current_step * 20,
                max=100,
                width="100%",
                color_scheme="indigo",
                radius="full"
            ),
            rx.text(
                "Polling execution status every 2 seconds via Reflex background event. Results will refresh immediately upon completion.",
                font_size="0.75rem",
                color="#64748b"
            ),
            spacing="3",
            width="100%"
        ),
        padding="1.25rem",
        border_radius="0.75rem",
        background_color="rgba(99, 102, 241, 0.1)",
        border="1px solid rgba(99, 102, 241, 0.3)",
        width="100%"
    )

def render_executive_summary() -> rx.Component:
    """Render the verified executive summary narrative and citation verification badge."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.hstack(
                    rx.icon(tag="sparkles", size=18, color="#818cf8"),
                    rx.text("Executive Summary Narrative", font_weight="700", font_size="1.1rem", color="#ffffff"),
                    spacing="2",
                    align_items="center"
                ),
                rx.spacer(),
                # Citation audit badge
                rx.badge(
                    f"Citation Audit: {AppState.verification_verified_count}/{AppState.verification_total_count} Verified ({AppState.verification_rate}%)",
                    color_scheme=rx.cond(AppState.verification_is_valid, "green", "amber"),
                    variant="solid",
                    size="2"
                ),
                spacing="3",
                align_items="center",
                width="100%"
            ),
            rx.divider(border_color="rgba(255, 255, 255, 0.08)"),
            rx.text(
                AppState.job_executive_summary,
                font_size="0.925rem",
                color="#e2e8f0",
                line_height="1.6"
            ),
            rx.cond(
                AppState.job_recommendations.length() > 0,
                rx.vstack(
                    rx.text("Strategic Recommendations:", font_weight="600", font_size="0.875rem", color="#93c5fd"),
                    rx.foreach(
                        AppState.job_recommendations,
                        lambda rec: rx.hstack(
                            rx.icon(tag="circle-check", size=14, color="#60a5fa"),
                            rx.text(rec, font_size="0.85rem", color="#cbd5e1"),
                            spacing="2",
                            align_items="flex-start"
                        )
                    ),
                    spacing="2",
                    margin_top="0.5rem",
                    width="100%"
                )
            ),
            spacing="3",
            align_items="flex-start",
            width="100%"
        ),
        padding="1.5rem",
        border_radius="0.75rem",
        background_color="rgba(15, 23, 42, 0.6)",
        border="1px solid rgba(255, 255, 255, 0.08)",
        width="100%"
    )

def render_explainability_panel() -> rx.Component:
    """Render the 'How the agent decided' run log audit trail."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.hstack(
                    rx.icon(tag="bot", size=18, color="#38bdf8"),
                    rx.text("How the Agent Decided (Explainability & Audit Trail)", font_weight="700", font_size="1rem", color="#ffffff"),
                    spacing="2",
                    align_items="center"
                ),
                rx.spacer(),
                rx.badge(f"{AppState.job_run_log.length()} Execution Steps", color_scheme="gray", variant="surface"),
                spacing="3",
                align_items="center",
                width="100%"
            ),
            rx.text(
                "Inspect every autonomous decision, LLM rationale, tool call, latency breakdown, and token usage.",
                font_size="0.8rem",
                color="#94a3b8"
            ),
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Step"),
                            rx.table.column_header_cell("Tool"),
                            rx.table.column_header_cell("Model Rationale"),
                            rx.table.column_header_cell("Model"),
                            rx.table.column_header_cell("Tool Time"),
                            rx.table.column_header_cell("LLM Latency"),
                            rx.table.column_header_cell("Tokens")
                        )
                    ),
                    rx.table.body(
                        rx.foreach(
                            AppState.job_run_log,
                            lambda step: rx.table.row(
                                rx.table.cell(rx.badge(f"#{step.step}", color_scheme="gray", variant="surface")),
                                rx.table.cell(rx.badge(step.tool, color_scheme="indigo", variant="soft")),
                                rx.table.cell(rx.text(step.rationale, font_size="0.8rem", color="#cbd5e1", max_width="380px")),
                                rx.table.cell(rx.text(step.model, font_size="0.75rem", color="#94a3b8")),
                                rx.table.cell(rx.text(f"{step.tool_time_ms} ms", font_size="0.75rem", color="#94a3b8")),
                                rx.table.cell(rx.text(f"{step.llm_latency_ms} ms", font_size="0.75rem", color="#38bdf8")),
                                rx.table.cell(rx.text(step.tokens, font_size="0.75rem", color="#a855f7"))
                            )
                        )
                    ),
                    variant="surface",
                    width="100%"
                ),
                overflow_x="auto",
                width="100%"
            ),
            spacing="3",
            width="100%"
        ),
        padding="1.5rem",
        border_radius="0.75rem",
        background_color="rgba(15, 23, 42, 0.6)",
        border="1px solid rgba(255, 255, 255, 0.08)",
        width="100%"
    )

def render_data_quality_panel() -> rx.Component:
    """Render comprehensive data quality panel with sentinels, domain invalids, suspected returns, and imputation."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.hstack(
                    rx.icon(tag="shield-alert", size=18, color="#f59e0b"),
                    rx.text("Data Quality & Cleaning Audit", font_weight="700", font_size="1rem", color="#ffffff"),
                    spacing="2",
                    align_items="center"
                ),
                rx.spacer(),
                rx.badge(f"Quality: {AppState.quality_score}/100", color_scheme="amber", variant="surface"),
                spacing="3",
                align_items="center",
                width="100%"
            ),
            rx.grid(
                rx.box(
                    rx.vstack(
                        rx.text("Sentinels Sanitized (>=3 repeats outside 3x IQR)", font_size="0.75rem", font_weight="600", color="#94a3b8"),
                        rx.cond(
                            AppState.sentinels_list.length() > 0,
                            rx.foreach(
                                AppState.sentinels_list,
                                lambda s: rx.hstack(
                                    rx.badge(s["column"].to_string(), color_scheme="gray", variant="soft"),
                                    rx.text(f"Value {s['value'].to_string()} ({s['count'].to_string()} rows)", font_size="0.75rem", color="#cbd5e1"),
                                    spacing="1"
                                )
                            ),
                            rx.text("None detected", font_size="0.75rem", color="#64748b")
                        ),
                        spacing="2",
                        width="100%"
                    ),
                    padding="1rem",
                    border_radius="0.5rem",
                    background_color="rgba(30, 41, 59, 0.3)",
                    border="1px solid rgba(255, 255, 255, 0.05)"
                ),
                rx.box(
                    rx.vstack(
                        rx.text("Domain Invalids Sanitized (Rule Violation)", font_size="0.75rem", font_weight="600", color="#94a3b8"),
                        rx.cond(
                            AppState.invalid_values_list.length() > 0,
                            rx.foreach(
                                AppState.invalid_values_list,
                                lambda iv: rx.hstack(
                                    rx.badge(iv["column"].to_string(), color_scheme="red", variant="soft"),
                                    rx.text(f"{iv['rule'].to_string()} ({iv['count'].to_string()} rows)", font_size="0.75rem", color="#cbd5e1"),
                                    spacing="1"
                                )
                            ),
                            rx.text("None detected", font_size="0.75rem", color="#64748b")
                        ),
                        spacing="2",
                        width="100%"
                    ),
                    padding="1rem",
                    border_radius="0.5rem",
                    background_color="rgba(30, 41, 59, 0.3)",
                    border="1px solid rgba(255, 255, 255, 0.05)"
                ),
                rx.box(
                    rx.vstack(
                        rx.text("Suspected Returns (Kept in Dataset)", font_size="0.75rem", font_weight="600", color="#94a3b8"),
                        rx.cond(
                            AppState.suspected_returns_list.length() > 0,
                            rx.foreach(
                                AppState.suspected_returns_list,
                                lambda sr: rx.hstack(
                                    rx.badge(sr["column"].to_string(), color_scheme="blue", variant="soft"),
                                    rx.text(f"{sr['count'].to_string()} return records kept", font_size="0.75rem", color="#cbd5e1"),
                                    spacing="1"
                                )
                            ),
                            rx.text("None detected", font_size="0.75rem", color="#64748b")
                        ),
                        spacing="2",
                        width="100%"
                    ),
                    padding="1rem",
                    border_radius="0.5rem",
                    background_color="rgba(30, 41, 59, 0.3)",
                    border="1px solid rgba(255, 255, 255, 0.05)"
                ),
                columns=rx.breakpoints(initial="1", sm="3"),
                spacing="3",
                width="100%"
            ),
            # Imputation rates table
            rx.cond(
                AppState.imputation_stats_list.length() > 0,
                rx.box(
                    rx.vstack(
                        rx.text("Column Imputation Rates & Missing Value Strategies", font_size="0.8rem", font_weight="600", color="#cbd5e1"),
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Column"),
                                    rx.table.column_header_cell("Imputed Rows"),
                                    rx.table.column_header_cell("Imputation Rate"),
                                    rx.table.column_header_cell("Strategy")
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    AppState.imputation_stats_list,
                                    lambda imp: rx.table.row(
                                        rx.table.cell(rx.badge(imp["column"].to_string(), color_scheme="gray")),
                                        rx.table.cell(rx.text(imp["count"].to_string(), font_size="0.8rem", color="#cbd5e1")),
                                        rx.table.cell(rx.badge(imp["rate"].to_string(), color_scheme="amber", variant="surface")),
                                        rx.table.cell(rx.text(imp["strategy"].to_string(), font_size="0.8rem", color="#94a3b8"))
                                    )
                                )
                            ),
                            variant="surface",
                            width="100%"
                        ),
                        spacing="2",
                        width="100%"
                    ),
                    width="100%",
                    margin_top="0.5rem"
                )
            ),
            spacing="3",
            width="100%"
        ),
        padding="1.5rem",
        border_radius="0.75rem",
        background_color="rgba(15, 23, 42, 0.6)",
        border="1px solid rgba(255, 255, 255, 0.08)",
        width="100%"
    )

def dashboard_page() -> rx.Component:
    AppState.active_tab = "dashboard"
    return app_layout(
        "Analytics Dashboard",
        rx.vstack(
            # Top KPI metrics
            rx.grid(
                stat_card("Dataset Quality", f"{AppState.quality_score}/100", "Composite benchmark", "award", "#10b981"),
                stat_card("Analyzed Rows", AppState.row_count, "Clean records", "layers", "#6366f1"),
                stat_card("Top Insights", AppState.job_insights.length(), "Ranked findings", "sparkles", "#38bdf8"),
                stat_card("Citation Audit", f"{AppState.verification_rate}%", "Factually grounded", "shield-check", "#a855f7"),
                columns=rx.breakpoints(initial="1", sm="2", lg="4"),
                spacing="4",
                width="100%"
            ),

            # Error Banner
            rx.cond(
                AppState.error_message != "",
                rx.box(
                    rx.hstack(
                        rx.icon(tag="triangle-alert", size=18, color="#ef4444"),
                        rx.text(AppState.error_message, font_size="0.85rem", color="#f87171"),
                        spacing="2",
                        align_items="center"
                    ),
                    padding="0.85rem 1.25rem",
                    border_radius="0.5rem",
                    background_color="rgba(239, 68, 68, 0.1)",
                    border="1px solid rgba(239, 68, 68, 0.3)",
                    width="100%"
                )
            ),

            # Progress panel when job is running
            rx.cond(
                AppState.job_status == "running",
                render_progress_panel()
            ),

            # Executive Summary (when completed or insights available)
            rx.cond(
                AppState.job_insights.length() > 0,
                rx.vstack(
                    render_executive_summary(),

                    # Ranked Insights Section
                    rx.box(
                        rx.vstack(
                            rx.hstack(
                                rx.icon(tag="sparkles", size=18, color="#818cf8"),
                                rx.text("Ranked Autonomous Insights (Top 8)", font_weight="700", font_size="1.1rem", color="#ffffff"),
                                rx.spacer(),
                                rx.badge("Impact Score Sorted", color_scheme="indigo", variant="surface"),
                                spacing="2",
                                align_items="center",
                                width="100%"
                            ),
                            rx.text(
                                "Each insight includes confidence classification, sample coverage (n_used/exclusion rate), caveats, and embedded visualization.",
                                font_size="0.85rem",
                                color="#94a3b8"
                            ),
                            rx.grid(
                                rx.foreach(AppState.job_insights, render_insight_card),
                                columns=rx.breakpoints(initial="1", md="2"),
                                spacing="4",
                                width="100%"
                            ),
                            spacing="4",
                            width="100%"
                        ),
                        padding="1.5rem",
                        border_radius="0.75rem",
                        background_color="rgba(15, 23, 42, 0.6)",
                        border="1px solid rgba(255, 255, 255, 0.08)",
                        width="100%"
                    ),

                    # Data Quality Panel
                    render_data_quality_panel(),

                    # Explainability Panel
                    render_explainability_panel(),

                    spacing="5",
                    width="100%"
                ),
                # Empty State
                rx.cond(
                    AppState.job_status != "running",
                    rx.box(
                        rx.vstack(
                            rx.icon(tag="file-bar-chart", size=36, color="#6366f1"),
                            rx.text("No Active Analysis Results", font_weight="700", font_size="1.1rem", color="#ffffff"),
                            rx.text(
                                "Select a dataset and start an autonomous analysis job to generate ranked insights, executive summary, recharts, and audit logs.",
                                font_size="0.85rem",
                                color="#94a3b8",
                                text_align="center",
                                max_width="500px"
                            ),
                            rx.link(
                                rx.button(
                                    rx.hstack(
                                        rx.icon(tag="upload", size=16),
                                        rx.text("Go to Upload & Start Analysis"),
                                        spacing="2"
                                    ),
                                    size="3",
                                    variant="solid",
                                    color_scheme="indigo"
                                ),
                                href="/upload"
                            ),
                            spacing="3",
                            align_items="center",
                            justify_content="center",
                            padding="3rem 1.5rem"
                        ),
                        border_radius="0.75rem",
                        background_color="rgba(15, 23, 42, 0.6)",
                        border="1px dashed rgba(255, 255, 255, 0.1)",
                        width="100%"
                    )
                )
            ),

            spacing="5",
            width="100%"
        )
    )
