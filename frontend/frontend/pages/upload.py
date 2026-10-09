"""Upload & Profiling page with Data Cleaning Diagnostics and Analysis Dispatch."""
import reflex as rx
from frontend.components.layout import app_layout
from frontend.components.stats_card import stat_card
from frontend.state import AppState


def sample_dataset_card(title: str, description: str, filename: str, icon_name: str) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag=icon_name, size=20, color="#818cf8"),
                rx.text(title, font_weight="600", font_size="0.95rem", color="#f8fafc"),
                spacing="2",
                align_items="center"
            ),
            rx.text(description, font_size="0.8rem", color="#94a3b8", line_height="1.4"),
            rx.button(
                rx.hstack(
                    rx.icon(tag="download", size=14),
                    rx.text("Load Benchmark Dataset"),
                    spacing="1",
                    align_items="center"
                ),
                size="1",
                variant="surface",
                color_scheme="indigo",
                width="100%",
                on_click=AppState.load_sample(filename)
            ),
            spacing="3",
            align_items="flex-start"
        ),
        padding="1rem",
        border_radius="0.65rem",
        background_color="rgba(30, 41, 59, 0.4)",
        border="1px solid rgba(255, 255, 255, 0.08)",
        _hover={"border_color": "rgba(99, 102, 241, 0.4)", "background_color": "rgba(30, 41, 59, 0.7)"},
        transition="all 0.2s ease",
        width="100%"
    )


def upload_zone() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.upload(
                rx.vstack(
                    rx.box(
                        rx.icon(tag="cloud-upload", size=36, color="#818cf8"),
                        padding="1rem",
                        border_radius="50%",
                        background_color="rgba(99, 102, 241, 0.1)"
                    ),
                    rx.text("Drag & drop your dataset here, or click to browse", font_weight="600", font_size="1rem", color="#f1f5f9"),
                    rx.text("Supports CSV, XLSX, XLS, and JSON files up to 50 MB", font_size="0.8rem", color="#64748b"),
                    rx.hstack(
                        rx.badge(".csv", color_scheme="gray"),
                        rx.badge(".xlsx", color_scheme="gray"),
                        rx.badge(".json", color_scheme="gray"),
                        spacing="2"
                    ),
                    spacing="3",
                    align_items="center",
                    justify_content="center",
                    padding="2.5rem",
                    width="100%"
                ),
                id="dataset_upload",
                border="2px dashed rgba(99, 102, 241, 0.35)",
                border_radius="0.75rem",
                background_color="rgba(15, 23, 42, 0.4)",
                padding="1rem",
                width="100%",
                _hover={"border_color": "#6366f1", "background_color": "rgba(99, 102, 241, 0.05)"},
                transition="all 0.2s ease"
            ),
            rx.hstack(
                rx.button(
                    rx.hstack(
                        rx.icon(tag="upload", size=16),
                        rx.text("Upload & Ingest Dataset"),
                        spacing="2",
                        align_items="center"
                    ),
                    size="3",
                    variant="solid",
                    color_scheme="indigo",
                    is_loading=AppState.is_uploading,
                    on_click=AppState.handle_upload(rx.upload_files(upload_id="dataset_upload"))
                ),
                rx.button(
                    "Clear Selection",
                    size="3",
                    variant="soft",
                    color_scheme="gray",
                    on_click=rx.clear_selected_files("dataset_upload")
                ),
                spacing="3",
                justify_content="center",
                width="100%",
                padding_top="0.5rem"
            ),
            spacing="3",
            width="100%"
        ),
        padding="1.5rem",
        border_radius="0.85rem",
        background_color="rgba(15, 23, 42, 0.6)",
        border="1px solid rgba(255, 255, 255, 0.08)",
        width="100%"
    )


def cleaning_report_panel() -> rx.Component:
    """Displays data cleaning diagnostics: sentinels, invalid values, returns, imputation."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon(tag="shield-check", size=20, color="#10b981"),
                    padding="0.4rem",
                    border_radius="0.4rem",
                    background_color="rgba(16, 185, 129, 0.15)"
                ),
                rx.vstack(
                    rx.text("Data Cleaning & Quality Diagnostics", font_weight="700", font_size="1.1rem", color="#ffffff"),
                    rx.text("Audit of detected placeholders, invalid domain bounds, returns, and deterministic imputation.", font_size="0.8rem", color="#94a3b8"),
                    spacing="0",
                    align_items="flex-start"
                ),
                spacing="3",
                align_items="center",
                width="100%"
            ),
            rx.divider(border_color="rgba(255, 255, 255, 0.08)"),

            # 4 Summary Badges
            rx.grid(
                rx.box(
                    rx.vstack(
                        rx.text("Placeholder Sentinels", font_size="0.75rem", color="#94a3b8"),
                        rx.text(f"{AppState.sentinels_list.length()} detected", font_weight="700", font_size="1rem", color="#ef4444"),
                        spacing="1"
                    ),
                    padding="0.75rem",
                    border_radius="0.5rem",
                    background_color="rgba(239, 68, 68, 0.08)",
                    border="1px solid rgba(239, 68, 68, 0.2)"
                ),
                rx.box(
                    rx.vstack(
                        rx.text("Domain Invalids", font_size="0.75rem", color="#94a3b8"),
                        rx.text(f"{AppState.invalid_values_list.length()} detected", font_weight="700", font_size="1rem", color="#f59e0b"),
                        spacing="1"
                    ),
                    padding="0.75rem",
                    border_radius="0.5rem",
                    background_color="rgba(245, 158, 11, 0.08)",
                    border="1px solid rgba(245, 158, 11, 0.2)"
                ),
                rx.box(
                    rx.vstack(
                        rx.text("Suspected Returns", font_size="0.75rem", color="#94a3b8"),
                        rx.text(f"{AppState.suspected_returns_list.length()} kept", font_weight="700", font_size="1rem", color="#06b6d4"),
                        spacing="1"
                    ),
                    padding="0.75rem",
                    border_radius="0.5rem",
                    background_color="rgba(6, 182, 212, 0.08)",
                    border="1px solid rgba(6, 182, 212, 0.2)"
                ),
                rx.box(
                    rx.vstack(
                        rx.text("Imputed Features", font_size="0.75rem", color="#94a3b8"),
                        rx.text(f"{AppState.imputation_stats_list.length()} columns", font_weight="700", font_size="1rem", color="#818cf8"),
                        spacing="1"
                    ),
                    padding="0.75rem",
                    border_radius="0.5rem",
                    background_color="rgba(99, 102, 241, 0.08)",
                    border="1px solid rgba(99, 102, 241, 0.2)"
                ),
                columns=rx.breakpoints(initial="2", md="4"),
                spacing="3",
                width="100%"
            ),

            # Sentinels Table (if any)
            rx.cond(
                AppState.sentinels_list.length() > 0,
                rx.box(
                    rx.vstack(
                        rx.text("Sanitized Placeholder Sentinels (Auto-converted to NaN & Imputed)", font_size="0.85rem", font_weight="600", color="#f87171"),
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Column"),
                                    rx.table.column_header_cell("Placeholder Value"),
                                    rx.table.column_header_cell("Occurrences"),
                                    rx.table.column_header_cell("Action")
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    AppState.sentinels_list,
                                    lambda s: rx.table.row(
                                        rx.table.cell(rx.text(s["column"], font_weight="600")),
                                        rx.table.cell(rx.badge(s["value"], color_scheme="red")),
                                        rx.table.cell(f"{s['count']} rows"),
                                        rx.table.cell(rx.badge("Converted to NaN & Imputed", color_scheme="red", variant="soft"))
                                    )
                                )
                            ),
                            variant="surface",
                            size="1",
                            width="100%"
                        ),
                        spacing="2",
                        width="100%"
                    ),
                    padding="1rem",
                    border_radius="0.5rem",
                    background_color="rgba(15, 23, 42, 0.4)",
                    border="1px solid rgba(255, 255, 255, 0.06)",
                    width="100%"
                )
            ),

            # Suspected Returns & Extremes (if any)
            rx.cond(
                AppState.suspected_returns_list.length() > 0,
                rx.box(
                    rx.vstack(
                        rx.text("Suspected Returns & Valid Extreme Values (Preserved in Dataset)", font_size="0.85rem", font_weight="600", color="#38bdf8"),
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Column"),
                                    rx.table.column_header_cell("Pattern"),
                                    rx.table.column_header_cell("Count"),
                                    rx.table.column_header_cell("Treatment")
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    AppState.suspected_returns_list,
                                    lambda sr: rx.table.row(
                                        rx.table.cell(rx.text(sr["column"], font_weight="600")),
                                        rx.table.cell("Negative values in quantity/count"),
                                        rx.table.cell(f"{sr['count']} rows"),
                                        rx.table.cell(rx.badge("Kept (Suspected Returns)", color_scheme="cyan", variant="soft"))
                                    )
                                )
                            ),
                            variant="surface",
                            size="1",
                            width="100%"
                        ),
                        spacing="2",
                        width="100%"
                    ),
                    padding="1rem",
                    border_radius="0.5rem",
                    background_color="rgba(15, 23, 42, 0.4)",
                    border="1px solid rgba(255, 255, 255, 0.06)",
                    width="100%"
                )
            ),

            # Imputation Rates Table
            rx.cond(
                AppState.imputation_stats_list.length() > 0,
                rx.box(
                    rx.vstack(
                        rx.text("Deterministic Imputation Rates by Column", font_size="0.85rem", font_weight="600", color="#a5b4fc"),
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Column"),
                                    rx.table.column_header_cell("Imputation Rate"),
                                    rx.table.column_header_cell("Rows Imputed"),
                                    rx.table.column_header_cell("Strategy")
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    AppState.imputation_stats_list,
                                    lambda imp: rx.table.row(
                                        rx.table.cell(rx.text(imp["column"], font_weight="600")),
                                        rx.table.cell(rx.badge(imp["rate"], color_scheme="amber", variant="surface")),
                                        rx.table.cell(rx.text(imp["count"].to_string(), " rows")),
                                        rx.table.cell(rx.badge(imp["strategy"], color_scheme="gray", variant="soft"))
                                    )
                                )
                            ),
                            variant="surface",
                            size="1",
                            width="100%"
                        ),
                        spacing="2",
                        width="100%"
                    ),
                    padding="1rem",
                    border_radius="0.5rem",
                    background_color="rgba(15, 23, 42, 0.4)",
                    border="1px solid rgba(255, 255, 255, 0.06)",
                    width="100%"
                )
            ),

            spacing="4",
            width="100%"
        ),
        padding="1.5rem",
        border_radius="0.75rem",
        background_color="rgba(15, 23, 42, 0.6)",
        border="1px solid rgba(255, 255, 255, 0.08)",
        width="100%"
    )


def start_analysis_dispatch_panel() -> rx.Component:
    """Prominent launch panel to start autonomous analysis."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon(tag="bot", size=24, color="#818cf8"),
                    padding="0.5rem",
                    border_radius="0.5rem",
                    background_color="rgba(99, 102, 241, 0.2)"
                ),
                rx.vstack(
                    rx.text("Launch Autonomous Analysis Agent", font_size="1.2rem", font_weight="700", color="#ffffff"),
                    rx.text("Dispatches the multi-step Plan-Act-Reflect orchestrator with statistical testing, insights, and citation audits.", font_size="0.825rem", color="#94a3b8"),
                    spacing="0",
                    align_items="flex-start"
                ),
                spacing="3",
                align_items="center",
                width="100%"
            ),
            rx.divider(border_color="rgba(255, 255, 255, 0.08)"),
            
            rx.vstack(
                rx.text("Analysis Objective / Goal", font_size="0.85rem", font_weight="600", color="#cbd5e1"),
                rx.input(
                    value=AppState.analysis_goal,
                    on_change=AppState.set_analysis_goal,
                    size="3",
                    width="100%",
                    variant="surface"
                ),
                rx.text("Guide the agent or leave default for comprehensive discovery across all dimensions.", font_size="0.75rem", color="#64748b"),
                spacing="1",
                align_items="flex-start",
                width="100%"
            ),

            rx.hstack(
                rx.button(
                    rx.hstack(
                        rx.icon(tag="play", size=18),
                        rx.text("Start Analysis", font_weight="700"),
                        spacing="2",
                        align_items="center"
                    ),
                    size="3",
                    variant="solid",
                    color_scheme="indigo",
                    is_loading=AppState.is_analyzing,
                    on_click=AppState.start_analysis
                ),
                rx.badge(f"Active Provider: {AppState.active_provider.upper()} ({AppState.active_model})", color_scheme="indigo", variant="surface", size="2"),
                spacing="3",
                align_items="center",
                width="100%",
                padding_top="0.5rem"
            ),
            spacing="4",
            width="100%"
        ),
        padding="1.5rem",
        border_radius="0.75rem",
        background_color="rgba(99, 102, 241, 0.08)",
        border="1px solid rgba(99, 102, 241, 0.25)",
        width="100%"
    )


def profile_results_view() -> rx.Component:
    """Full profile, cleaning report, and launch controls for active dataset."""
    return rx.vstack(
        # Action Toolbar
        rx.hstack(
            rx.vstack(
                rx.text("Data Profile & Diagnostics", font_size="1.2rem", font_weight="700", color="#ffffff"),
                rx.text(AppState.selected_dataset_name, font_size="0.85rem", color="#818cf8"),
                spacing="0",
                align_items="flex-start"
            ),
            rx.spacer(),
            rx.hstack(
                rx.button(
                    rx.hstack(
                        rx.icon(tag="sparkles", size=16),
                        rx.text("Clean Data"),
                        spacing="2",
                        align_items="center"
                    ),
                    size="2",
                    variant="surface",
                    color_scheme="amber",
                    is_loading=AppState.is_cleaning,
                    on_click=AppState.run_cleaning
                ),
                rx.button(
                    rx.hstack(
                        rx.icon(tag="refresh-cw", size=16),
                        rx.text("Re-profile"),
                        spacing="2",
                        align_items="center"
                    ),
                    size="2",
                    variant="surface",
                    color_scheme="indigo",
                    is_loading=AppState.is_profiling,
                    on_click=AppState.run_profiling
                ),
                spacing="3"
            ),
            width="100%",
            align_items="center",
            padding_bottom="0.5rem",
            border_bottom="1px solid rgba(255, 255, 255, 0.08)"
        ),
        
        # Start Analysis Button Panel
        start_analysis_dispatch_panel(),

        # Metric Cards Grid
        rx.grid(
            stat_card("Data Quality Score", f"{AppState.quality_score}/100", "Composite health score", "shield-check", "#10b981"),
            stat_card("Total Rows", AppState.row_count, "Parsed records", "table", "#6366f1"),
            stat_card("Total Columns", AppState.column_count, "Features / fields", "columns-3", "#38bdf8"),
            stat_card("Duplicate Rows", AppState.duplicate_rows, "Redundant records", "copy", "#f59e0b"),
            columns=rx.breakpoints(initial="1", sm="2", lg="4"),
            spacing="4",
            width="100%"
        ),

        # Cleaning Report Panel
        cleaning_report_panel(),
        
        # Warnings & Quality Feedback
        rx.cond(
            AppState.quality_warnings.length() > 0,
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.icon(tag="triangle-alert", size=18, color="#f59e0b"),
                        rx.text("Data Quality Alerts & Observations", font_weight="600", font_size="0.9rem", color="#fbbf24"),
                        spacing="2",
                        align_items="center"
                    ),
                    rx.vstack(
                        rx.foreach(
                            AppState.quality_warnings,
                            lambda w: rx.hstack(
                                rx.box(width="6px", height="6px", border_radius="50%", background_color="#f59e0b"),
                                rx.text(w, font_size="0.825rem", color="#cbd5e1"),
                                spacing="2",
                                align_items="center"
                            )
                        ),
                        spacing="1",
                        align_items="flex-start",
                        padding_left="0.5rem"
                    ),
                    spacing="2",
                    align_items="flex-start"
                ),
                padding="1rem",
                border_radius="0.65rem",
                background_color="rgba(245, 158, 11, 0.08)",
                border="1px solid rgba(245, 158, 11, 0.25)",
                width="100%"
            )
        ),

        # Column Profiles Breakdown
        rx.box(
            rx.vstack(
                rx.text("Column Specifications & Distributions", font_weight="600", font_size="1rem", color="#f1f5f9"),
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Column Name"),
                            rx.table.column_header_cell("Type"),
                            rx.table.column_header_cell("Null %"),
                            rx.table.column_header_cell("Cardinality"),
                            rx.table.column_header_cell("Statistical Summary"),
                            rx.table.column_header_cell("Status")
                        )
                    ),
                    rx.table.body(
                        rx.foreach(
                            AppState.column_profiles,
                            lambda col: rx.table.row(
                                rx.table.cell(rx.text(col["name"], font_weight="600", color="#ffffff")),
                                rx.table.cell(rx.badge(col["type"], color_scheme="indigo")),
                                rx.table.cell(col["null_pct"]),
                                rx.table.cell(col["unique"]),
                                rx.table.cell(rx.text(col["summary"], font_size="0.775rem", color="#94a3b8")),
                                rx.table.cell(
                                    rx.cond(
                                        col["warnings"] == "Clean",
                                        rx.badge("Clean", color_scheme="green"),
                                        rx.badge("Flagged", color_scheme="amber")
                                    )
                                )
                            )
                        )
                    ),
                    variant="surface",
                    width="100%"
                ),
                spacing="3",
                align_items="flex-start",
                width="100%"
            ),
            padding="1.25rem",
            border_radius="0.75rem",
            background_color="rgba(15, 23, 42, 0.6)",
            border="1px solid rgba(255, 255, 255, 0.08)",
            width="100%"
        ),
        
        spacing="4",
        width="100%"
    )


def upload_page() -> rx.Component:
    return app_layout(
        "Data Ingestion & Profiling",
        rx.vstack(
            # Status / Error Alert Messages
            rx.cond(
                AppState.status_message != "",
                rx.callout(
                    AppState.status_message,
                    icon="info",
                    color_scheme="indigo",
                    variant="soft",
                    width="100%"
                )
            ),
            rx.cond(
                AppState.error_message != "",
                rx.callout(
                    AppState.error_message,
                    icon="circle-alert",
                    color_scheme="red",
                    variant="soft",
                    width="100%"
                )
            ),
            
            # File Upload Zone
            upload_zone(),
            
            # Benchmark Sample Datasets Section
            rx.box(
                rx.vstack(
                    rx.text("QUICK TEST BENCHMARK DATASETS (PLAN §8.1)", font_size="0.75rem", font_weight="700", color="#818cf8", letter_spacing="0.06em"),
                    rx.grid(
                        sample_dataset_card(
                            "Retail & E-Commerce Sales",
                            "Contains duplicate orders, formatted currency strings ($), mixed date formats, and negative/outlier quantities.",
                            "retail_sales_messy.csv",
                            "shopping-cart"
                        ),
                        sample_dataset_card(
                            "HR Employee Attrition",
                            "Features department casing variations ('sales' vs 'Sales'), missing salaries, tenure nulls, and age outliers.",
                            "hr_attrition_messy.csv",
                            "users"
                        ),
                        sample_dataset_card(
                            "Digital Marketing Campaigns",
                            "Includes spend currency symbols, null conversion metrics, duplicate campaign tags, and inconsistent date timestamps.",
                            "marketing_campaign_messy.csv",
                            "trending-up"
                        ),
                        columns=rx.breakpoints(initial="1", md="3"),
                        spacing="3",
                        width="100%"
                    ),
                    spacing="2",
                    align_items="flex-start",
                    width="100%"
                ),
                width="100%",
                padding_y="0.5rem"
            ),
            
            # Profile & Cleaning Results View
            rx.cond(
                AppState.selected_dataset_id != "",
                profile_results_view(),
                rx.box(
                    rx.vstack(
                        rx.icon(tag="file-question", size=36, color="#475569"),
                        rx.text("No dataset currently loaded", font_weight="600", color="#94a3b8"),
                        rx.text("Upload a file above or click one of the benchmark datasets to begin profiling.", font_size="0.85rem", color="#64748b"),
                        spacing="2",
                        align_items="center",
                        padding="3rem"
                    ),
                    border="1px dashed rgba(255, 255, 255, 0.08)",
                    border_radius="0.75rem",
                    width="100%"
                )
            ),
            
            spacing="5",
            width="100%"
        )
    )
