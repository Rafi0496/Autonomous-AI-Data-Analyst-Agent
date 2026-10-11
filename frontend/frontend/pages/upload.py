"""Upload & Data Quality Screen: Neumorphic Inset Dropzone, Diagnostics, and Analysis Dispatch."""
import reflex as rx
from frontend.components.layout import app_layout
from frontend.components.neu_components import (
    empty_state,
    neu_button,
    neu_card,
    neu_input,
    neu_inset_card,
    progress_track,
    status_pill,
)
from frontend.state import AppState
from frontend.theme import (
    ACCENT_COLOR,
    FONT_SERIF,
    RADIUS_FULL,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    RADIUS_XL,
    SHADOW_INSET,
    SHADOW_RAISED,
    SHADOW_RAISED_SM,
    SURFACE_COLOR,
    TEXT_COLOR,
    TEXT_MUTED,
)


def sample_dataset_card(title: str, description: str, filename: str, icon_name: str) -> rx.Component:
    """Benchmark dataset card with raised Neumorphic styling."""
    return neu_card(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon(tag=icon_name, size=18, color=ACCENT_COLOR),
                    padding="0.45rem",
                    border_radius=RADIUS_MD,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_RAISED_SM,
                ),
                rx.text(title, font_weight="600", font_size="0.9rem", color=TEXT_COLOR),
                spacing="2",
                align_items="center",
            ),
            rx.text(description, font_size="0.775rem", color=TEXT_MUTED, line_height="1.4"),
            rx.spacer(),
            neu_button(
                rx.hstack(
                    rx.icon(tag="download", size=13),
                    rx.text("Load Benchmark", font_size="0.75rem"),
                    spacing="1",
                    align_items="center",
                ),
                variant="secondary",
                width="100%",
                padding="0.45rem",
                on_click=AppState.load_sample(filename),
            ),
            spacing="3",
            align_items="flex-start",
            height="100%",
        ),
        sm=True,
        width="100%",
    )


def upload_zone() -> rx.Component:
    """Sunken/inset upload drop zone with dual tonal shadows and dashed border."""
    return neu_inset_card(
        rx.vstack(
            rx.upload(
                rx.vstack(
                    rx.box(
                        rx.icon(tag="cloud-upload", size=32, color=ACCENT_COLOR),
                        padding="0.85rem",
                        border_radius=RADIUS_FULL,
                        background_color=SURFACE_COLOR,
                        box_shadow=SHADOW_RAISED_SM,
                    ),
                    rx.text("Drop your dataset here, or click to browse", font_weight="600", font_size="0.95rem", color=TEXT_COLOR),
                    rx.text("Supports CSV, XLSX, XLS, and JSON files up to 50 MB", font_size="0.775rem", color=TEXT_MUTED),
                    rx.hstack(
                        status_pill(".csv", icon="file-spreadsheet"),
                        status_pill(".xlsx", icon="file-spreadsheet"),
                        status_pill(".json", icon="file-code"),
                        spacing="2",
                    ),
                    spacing="2",
                    align_items="center",
                    justify_content="center",
                    padding="2rem 1rem",
                    width="100%",
                ),
                id="dataset_upload",
                border="2px dashed var(--shadow-light)",
                border_radius=RADIUS_LG,
                background_color="transparent",
                padding="0.5rem",
                width="100%",
                cursor="pointer",
            ),
            rx.hstack(
                neu_button(
                    rx.hstack(
                        rx.icon(tag="upload", size=15),
                        rx.text("Upload & Ingest"),
                        spacing="2",
                        align_items="center",
                    ),
                    variant="primary",
                    is_loading=AppState.is_uploading,
                    on_click=AppState.handle_upload(rx.upload_files(upload_id="dataset_upload")),
                ),
                neu_button(
                    "Clear Selection",
                    variant="secondary",
                    on_click=rx.clear_selected_files("dataset_upload"),
                ),
                spacing="3",
                justify_content="center",
                width="100%",
                padding_top="0.5rem",
            ),
            spacing="3",
            width="100%",
            align_items="center",
        ),
        width="100%",
    )


def data_quality_score_card() -> rx.Component:
    """Prominent raw data quality and sanitization score banner."""
    return neu_card(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.hstack(
                        rx.icon(tag="shield-check", size=18, color="var(--status-success)"),
                        rx.text("Raw Data Quality Score", font_weight="700", font_size="1.05rem", color=TEXT_COLOR),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.text(
                        "Statistical hygiene score evaluating completeness, validity, and sentinel presence.",
                        font_size="0.8rem",
                        color=TEXT_MUTED,
                    ),
                    spacing="1",
                    align_items="flex-start",
                ),
                rx.spacer(),
                rx.box(
                    rx.text(f"{AppState.quality_score}/100", font_size="1.4rem", font_weight="700", color=ACCENT_COLOR),
                    padding="0.5rem 1rem",
                    border_radius=RADIUS_LG,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_INSET,
                ),
                width="100%",
                align_items="center",
            ),
            # Progress gauge
            progress_track(
                percent=AppState.quality_score,
                height="10px",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def cleaning_summary_card() -> rx.Component:
    """Displays what was cleaned, imputed, and excluded per the API response."""
    return neu_card(
        rx.vstack(
            rx.hstack(
                rx.icon(tag="sparkles", size=18, color=ACCENT_COLOR),
                rx.text("Cleaning & Imputation Summary", font_weight="700", font_size="1rem", color=TEXT_COLOR),
                rx.spacer(),
                status_pill("Deterministic Normalization", icon="check"),
                width="100%",
                align_items="center",
            ),
            rx.text(
                "Audit trail of sanitized sentinels, preserved business returns, and mode/median imputations.",
                font_size="0.8rem",
                color=TEXT_MUTED,
            ),

            # 4 Summary Stat Pills
            rx.grid(
                neu_inset_card(
                    rx.vstack(
                        rx.text("Sentinels Cleared", font_size="0.75rem", color=TEXT_MUTED),
                        rx.text(f"{AppState.sentinels_list.length()}", font_weight="700", font_size="1.1rem", color="var(--status-error)"),
                        spacing="0",
                    ),
                    padding="0.75rem",
                ),
                neu_inset_card(
                    rx.vstack(
                        rx.text("Domain Invalids", font_size="0.75rem", color=TEXT_MUTED),
                        rx.text(f"{AppState.invalid_values_list.length()}", font_weight="700", font_size="1.1rem", color="var(--status-warning)"),
                        spacing="0",
                    ),
                    padding="0.75rem",
                ),
                neu_inset_card(
                    rx.vstack(
                        rx.text("Suspected Returns", font_size="0.75rem", color=TEXT_MUTED),
                        rx.text(f"{AppState.suspected_returns_list.length()}", font_weight="700", font_size="1.1rem", color="var(--status-info)"),
                        spacing="0",
                    ),
                    padding="0.75rem",
                ),
                neu_inset_card(
                    rx.vstack(
                        rx.text("Imputed Features", font_size="0.75rem", color=TEXT_MUTED),
                        rx.text(f"{AppState.imputation_stats_list.length()}", font_weight="700", font_size="1.1rem", color=ACCENT_COLOR),
                        spacing="0",
                    ),
                    padding="0.75rem",
                ),
                columns=rx.breakpoints(initial="2", sm="4"),
                spacing="3",
                width="100%",
            ),

            # Sentinels Table (if any)
            rx.cond(
                AppState.sentinels_list.length() > 0,
                neu_inset_card(
                    rx.vstack(
                        rx.text("Detected Sentinel Placeholders (Converted to NaN)", font_size="0.8rem", font_weight="600", color="var(--status-error)"),
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Column"),
                                    rx.table.column_header_cell("Placeholder Value"),
                                    rx.table.column_header_cell("Count"),
                                    rx.table.column_header_cell("Action"),
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    AppState.sentinels_list,
                                    lambda s: rx.table.row(
                                        rx.table.cell(rx.text(s["column"], font_weight="600")),
                                        rx.table.cell(status_pill(s["value"].to_string(), icon="hash", status="error")),
                                        rx.table.cell(f"{s['count']} rows"),
                                        rx.table.cell(rx.text("Sanitized & imputed", color=TEXT_MUTED, font_size="0.75rem")),
                                    ),
                                )
                            ),
                            variant="surface",
                            size="1",
                            width="100%",
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    padding="0.85rem",
                    width="100%",
                ),
            ),

            # Imputation Rates Table (if any)
            rx.cond(
                AppState.imputation_stats_list.length() > 0,
                neu_inset_card(
                    rx.vstack(
                        rx.text("Imputed Columns & Strategy", font_size="0.8rem", font_weight="600", color=ACCENT_COLOR),
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Column"),
                                    rx.table.column_header_cell("Strategy"),
                                    rx.table.column_header_cell("Imputation Rate"),
                                    rx.table.column_header_cell("Imputed Rows"),
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    AppState.imputation_stats_list,
                                    lambda imp: rx.table.row(
                                        rx.table.cell(rx.text(imp["column"], font_weight="600")),
                                        rx.table.cell(status_pill(imp["strategy"], icon="calculator")),
                                        rx.table.cell(rx.text(imp["rate"], font_weight="600", color=ACCENT_COLOR)),
                                        rx.table.cell(f"{imp['count']} rows"),
                                    ),
                                )
                            ),
                            variant="surface",
                            size="1",
                            width="100%",
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    padding="0.85rem",
                    width="100%",
                ),
            ),

            spacing="4",
            width="100%",
        ),
        width="100%",
    )


def run_analysis_cta_card() -> rx.Component:
    """Primary Action: 'Run analysis' card initiating autonomous analysis."""
    return neu_card(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon(tag="bot", size=22, color="#ffffff"),
                    padding="0.55rem",
                    border_radius=RADIUS_FULL,
                    background_color=ACCENT_COLOR,
                    box_shadow=SHADOW_RAISED_SM,
                ),
                rx.vstack(
                    rx.text("Ready for Autonomous Analysis", font_weight="700", font_size="1.1rem", color=TEXT_COLOR),
                    rx.text(
                        "Dispatch the autonomous agent to explore correlations, segment variations, and statistical anomalies.",
                        font_size="0.8rem",
                        color=TEXT_MUTED,
                    ),
                    spacing="0",
                    align_items="flex-start",
                ),
                width="100%",
                align_items="center",
            ),
            rx.vstack(
                rx.text("Analysis Goal / Focus Area", font_size="0.8rem", color=TEXT_MUTED, font_weight="500"),
                neu_input(
                    value=AppState.analysis_goal,
                    on_change=AppState.set_analysis_goal,
                    placeholder="E.g., Identify revenue drivers, regional variations, and outliers...",
                ),
                spacing="1",
                width="100%",
            ),
            rx.hstack(
                neu_button(
                    rx.hstack(
                        rx.icon(tag="play", size=16),
                        rx.text("Run Analysis", font_weight="600"),
                        spacing="2",
                        align_items="center",
                    ),
                    variant="primary",
                    is_loading=AppState.is_analyzing,
                    padding="0.75rem 1.5rem",
                    on_click=AppState.start_analysis,
                ),
                status_pill(f"Provider: {AppState.active_provider.upper()}", icon="cpu"),
                spacing="3",
                align_items="center",
                width="100%",
                padding_top="0.25rem",
            ),
            spacing="3",
            width="100%",
        ),
        width="100%",
    )


def upload_page() -> rx.Component:
    """Upload & Data Quality Screen."""
    return app_layout(
        "Datasets & Quality",
        rx.vstack(
            # Status Alerts
            rx.cond(
                AppState.status_message != "",
                rx.callout(
                    AppState.status_message,
                    icon="info",
                    color_scheme="gray",
                    size="1",
                    width="100%",
                ),
            ),
            rx.cond(
                AppState.error_message != "",
                rx.callout(
                    AppState.error_message,
                    icon="circle-alert",
                    color_scheme="red",
                    size="1",
                    width="100%",
                ),
            ),

            # 1. Inset Upload Drop Zone
            upload_zone(),

            # 2. Benchmark Quick Datasets
            rx.vstack(
                rx.text(
                    "PRELOADED BENCHMARK DATASETS",
                    font_size="0.75rem",
                    font_weight="700",
                    color=TEXT_MUTED,
                    letter_spacing="0.08em",
                    padding_x="0.25rem",
                ),
                rx.grid(
                    sample_dataset_card(
                        "Retail & Commercial Sales",
                        "Contains duplicate orders, formatted currency strings, mixed dates, and return records.",
                        "retail_sales_messy.csv",
                        "shopping-cart",
                    ),
                    sample_dataset_card(
                        "HR Workforce & Attrition",
                        "Features department casing variations, missing salaries, tenure nulls, and age bounds.",
                        "hr_attrition_messy.csv",
                        "users",
                    ),
                    sample_dataset_card(
                        "Digital Marketing Campaigns",
                        "Includes spend currency symbols, null conversion metrics, duplicate campaign tags.",
                        "marketing_campaign_messy.csv",
                        "trending-up",
                    ),
                    columns=rx.breakpoints(initial="1", md="3"),
                    spacing="3",
                    width="100%",
                ),
                spacing="2",
                width="100%",
                padding_top="1rem",
            ),

            # 3. Active Dataset Profile & Cleaning Diagnostics
            rx.cond(
                AppState.selected_dataset_id != "",
                rx.vstack(
                    # Primary CTA
                    run_analysis_cta_card(),
                    # Quality Score
                    data_quality_score_card(),
                    # 4 Dimension Cards
                    rx.grid(
                        neu_card(
                            rx.vstack(
                                rx.text("Total Rows", font_size="0.75rem", color=TEXT_MUTED),
                                rx.text(f"{AppState.row_count}", font_size="1.25rem", font_weight="700", color=TEXT_COLOR),
                                rx.text("Cleaned records", font_size="0.7rem", color=TEXT_MUTED),
                                spacing="0",
                            ),
                            sm=True,
                        ),
                        neu_card(
                            rx.vstack(
                                rx.text("Total Columns", font_size="0.75rem", color=TEXT_MUTED),
                                rx.text(f"{AppState.column_count}", font_size="1.25rem", font_weight="700", color=TEXT_COLOR),
                                rx.text("Evaluated features", font_size="0.7rem", color=TEXT_MUTED),
                                spacing="0",
                            ),
                            sm=True,
                        ),
                        neu_card(
                            rx.vstack(
                                rx.text("Duplicates", font_size="0.75rem", color=TEXT_MUTED),
                                rx.text(f"{AppState.duplicate_rows}", font_size="1.25rem", font_weight="700", color=TEXT_COLOR),
                                rx.text("Removed in cleaning", font_size="0.7rem", color=TEXT_MUTED),
                                spacing="0",
                            ),
                            sm=True,
                        ),
                        neu_card(
                            rx.vstack(
                                rx.text("Missing Cells", font_size="0.75rem", color=TEXT_MUTED),
                                rx.text(f"{AppState.missing_percentage}%", font_size="1.25rem", font_weight="700", color=TEXT_COLOR),
                                rx.text("Overall missingness", font_size="0.7rem", color=TEXT_MUTED),
                                spacing="0",
                            ),
                            sm=True,
                        ),
                        columns=rx.breakpoints(initial="2", sm="4"),
                        spacing="3",
                        width="100%",
                    ),
                    # Cleaning Report Card
                    cleaning_summary_card(),
                    spacing="4",
                    width="100%",
                    padding_top="1rem",
                ),
                empty_state(
                    title="No Active Dataset",
                    description="Upload a CSV or select one of the benchmark datasets above to inspect data quality.",
                    icon="database",
                ),
            ),
            spacing="4",
            width="100%",
        ),
        max_width="820px",
    )
