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

def profile_results_view() -> rx.Component:
    """Data profile results view driven by AppState."""
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
                        rx.text("Run Data Cleaning"),
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
            padding_bottom="1rem",
            border_bottom="1px solid rgba(255, 255, 255, 0.08)"
        ),
        
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
        
        # Warnings & Quality Feedback
        rx.cond(
            AppState.quality_warnings.length() > 0,
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.icon(tag="alert-triangle", size=18, color="#f59e0b"),
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
    AppState.active_tab = "upload"
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
                    icon="alert-circle",
                    color_scheme="red",
                    variant="soft",
                    width="100%"
                )
            ),
            
            # File Upload Zone
            upload_zone(),
            
            # Benchmark Sample Datasets Section (Phase 1 §8.1)
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
            
            # Profile Results View (Shown if dataset selected)
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
