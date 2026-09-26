import reflex as rx
from frontend.components.layout import app_layout
from frontend.components.stats_card import stat_card
from frontend.state import AppState

def dashboard_page() -> rx.Component:
    AppState.active_tab = "dashboard"
    return app_layout(
        "Analytics Dashboard",
        rx.vstack(
            # Top KPI metrics
            rx.grid(
                stat_card("Dataset Quality", f"{AppState.quality_score}/100", "Composite benchmark", "award", "#10b981"),
                stat_card("Analyzed Rows", AppState.row_count, "Clean records", "layers", "#6366f1"),
                stat_card("Total Dimensions", AppState.column_count, "Attributes", "grid-2x2", "#38bdf8"),
                stat_card("Memory Footprint", f"{AppState.memory_mb} MB", "In-memory cache", "hard-drive", "#a855f7"),
                columns=rx.breakpoints(initial="1", sm="2", lg="4"),
                spacing="4",
                width="100%"
            ),
            
            # Autonomous Findings / Insight Cards placeholder for Phase 2/3
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.box(
                            rx.icon(tag="sparkles", size=18, color="#818cf8"),
                            padding="0.4rem",
                            border_radius="0.4rem",
                            background_color="rgba(99, 102, 241, 0.15)"
                        ),
                        rx.vstack(
                            rx.text("Autonomous Insights & Statistical Findings", font_weight="700", font_size="1.1rem", color="#ffffff"),
                            rx.text("Driven by Plan-Act-Reflect Agent Core (Phase 2)", font_size="0.8rem", color="#94a3b8"),
                            spacing="0",
                            align_items="flex-start"
                        ),
                        rx.spacer(),
                        rx.badge("Phase 2 Orchestrator", color_scheme="indigo", variant="surface"),
                        spacing="3",
                        align_items="center",
                        width="100%"
                    ),
                    rx.box(
                        rx.vstack(
                            rx.text("Foundational Pipeline Active", font_weight="600", color="#f1f5f9"),
                            rx.text(
                                "The deterministic data profiling and cleaning pipelines are fully operational. "
                                "In Phase 2, the Claude API Plan-Act-Reflect engine will execute correlation, segment comparison, and anomaly detection over these profiles.",
                                font_size="0.85rem",
                                color="#94a3b8",
                                max_width="700px"
                            ),
                            rx.link(
                                rx.button(
                                    rx.hstack(
                                        rx.icon(tag="arrow-left", size=14),
                                        rx.text("Inspect Profile / Upload More Datasets"),
                                        spacing="2"
                                    ),
                                    size="2",
                                    variant="soft",
                                    color_scheme="indigo"
                                ),
                                href="/upload"
                            ),
                            spacing="3",
                            align_items="flex-start",
                            padding="1.5rem"
                        ),
                        background_color="rgba(30, 41, 59, 0.3)",
                        border_radius="0.65rem",
                        border="1px dashed rgba(255, 255, 255, 0.1)",
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

            # Data Table Preview
            rx.cond(
                AppState.preview_rows.length() > 0,
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.text("Dataset Sample Preview (Head)", font_weight="600", font_size="1rem", color="#f1f5f9"),
                            rx.spacer(),
                            rx.badge(f"{AppState.row_count} total records", color_scheme="gray"),
                            width="100%",
                            align_items="center"
                        ),
                        rx.box(
                            rx.table.root(
                                rx.table.header(
                                    rx.table.row(
                                        rx.foreach(
                                            AppState.preview_columns,
                                            lambda c: rx.table.column_header_cell(c)
                                        )
                                    )
                                ),
                                rx.table.body(
                                    rx.foreach(
                                        AppState.preview_rows,
                                        lambda row: rx.table.row(
                                            rx.foreach(
                                                AppState.preview_columns,
                                                lambda col_name: rx.table.cell(rx.text(row[col_name].to_string(), font_size="0.8rem", color="#cbd5e1"))
                                            )
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
                    padding="1.25rem",
                    border_radius="0.75rem",
                    background_color="rgba(15, 23, 42, 0.6)",
                    border="1px solid rgba(255, 255, 255, 0.08)",
                    width="100%"
                )
            ),

            spacing="5",
            width="100%"
        )
    )
