"""Interactive Report Generation and Export page for Autonomous AI Data Analyst Agent.
Neo-morphism 60% + Minimalism 40% with dual PDF and Word export dispatchers,
active job linking, and past reports repository.
"""
from typing import Any, Dict
import reflex as rx
from frontend.components.layout import app_layout
from frontend.components.neu_components import (
    empty_state,
    neu_button,
    neu_card,
    neu_inset_card,
    status_pill,
)
from frontend.state import AppState, ReportItemModel, API_BASE_URL
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


def report_card(
    title: str,
    description: str,
    format_tag: str,
    icon: str,
    on_click: Any,
    variant: str = "primary",
) -> rx.Component:
    """Card for generating an executive business report."""
    return neu_card(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon(tag=icon, size=20, color=ACCENT_COLOR),
                    padding="0.6rem",
                    border_radius=RADIUS_FULL,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_INSET,
                ),
                rx.vstack(
                    rx.text(title, font_size="0.95rem", font_weight="600", color=TEXT_COLOR),
                    rx.text(description, font_size="0.78rem", color=TEXT_MUTED, line_height="1.4"),
                    spacing="0",
                    align_items="flex-start",
                ),
                rx.spacer(),
                rx.box(
                    rx.text(format_tag, font_size="0.7rem", font_weight="700", color=ACCENT_COLOR),
                    padding="0.2rem 0.5rem",
                    border_radius=RADIUS_SM,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_RAISED_SM,
                ),
                spacing="3",
                align_items="center",
                width="100%",
            ),
            neu_button(
                rx.hstack(
                    rx.icon(tag="file-down", size=14),
                    rx.text(f"Generate & Export {format_tag}"),
                    spacing="2",
                    align_items="center",
                ),
                variant=variant,
                is_loading=AppState.is_generating_report,
                on_click=on_click,
                width="100%",
            ),
            spacing="3",
            align_items="flex-start",
            width="100%",
        ),
        width="100%",
    )


def past_report_row(rep: ReportItemModel) -> rx.Component:
    """Row in past reports table."""
    return rx.table.row(
        rx.table.cell(
            rx.hstack(
                rx.icon(
                    tag=rx.cond(rep.format == "pdf", "file-text", "file-spreadsheet"),
                    size=14,
                    color=ACCENT_COLOR,
                ),
                rx.text(rep.filename, font_size="0.825rem", font_weight="600", color=TEXT_COLOR),
                spacing="2",
                align_items="center",
            )
        ),
        rx.table.cell(rx.text(rep.dataset_name, font_size="0.8rem", color=TEXT_MUTED)),
        rx.table.cell(
            rx.box(
                rx.text(rep.format.upper(), font_size="0.7rem", font_weight="700", color=TEXT_COLOR),
                background_color=SURFACE_COLOR,
                box_shadow=SHADOW_INSET,
                padding="0.15rem 0.45rem",
                border_radius=RADIUS_SM,
                display="inline-block",
            )
        ),
        rx.table.cell(rx.text(rep.created_at, font_size="0.75rem", color=TEXT_MUTED)),
        rx.table.cell(
            rx.link(
                neu_button(
                    rx.hstack(
                        rx.icon(tag="download", size=12),
                        rx.text("Download"),
                        spacing="1",
                        align_items="center",
                    ),
                    variant="secondary",
                    padding="0.3rem 0.65rem",
                ),
                href=f"{API_BASE_URL.replace('/api/v1', '')}{rep.download_url}",
                is_external=True,
            )
        ),
    )


def reports_page() -> rx.Component:
    """Report Generation & Export Screen."""
    return app_layout(
        "Reports",
        rx.vstack(
            # 1. Header Card
            neu_card(
                rx.vstack(
                    rx.hstack(
                        rx.hstack(
                            rx.box(
                                rx.icon(tag="file-text", size=18, color=ACCENT_COLOR),
                                padding="0.55rem",
                                border_radius=RADIUS_FULL,
                                background_color=SURFACE_COLOR,
                                box_shadow=SHADOW_INSET,
                            ),
                            rx.vstack(
                                rx.text("Export Business Intelligence Reports", font_size="1.05rem", font_weight="600", color=TEXT_COLOR),
                                rx.text(
                                    f"Dataset: {AppState.selected_dataset_name} | Publication-ready executive summaries with charts and methodology audit trail.",
                                    font_size="0.78rem",
                                    color=TEXT_MUTED,
                                ),
                                spacing="0",
                                align_items="flex-start",
                            ),
                            spacing="3",
                            align_items="center",
                        ),
                        rx.spacer(),
                        rx.cond(
                            AppState.active_job_id != "",
                            status_pill("Job Linked", icon="link", status="success"),
                            status_pill("No Active Job", icon="circle-alert", status="warn"),
                        ),
                        spacing="3",
                        align_items="center",
                        width="100%",
                    ),
                    spacing="2",
                    align_items="flex-start",
                    width="100%",
                ),
                width="100%",
            ),

            # Error banner if report generation fails
            rx.cond(
                AppState.error_message != "",
                neu_card(
                    rx.hstack(
                        rx.icon(tag="circle-alert", size=16, color="var(--status-error)"),
                        rx.text(AppState.error_message, font_size="0.825rem", color="var(--status-error)"),
                        spacing="2",
                        align_items="center",
                    ),
                    width="100%",
                ),
            ),

            # 2. Dual Generation Cards Grid (PDF & Word)
            rx.grid(
                report_card(
                    title="Executive Summary PDF",
                    description="Stylized presentation-grade report with inline charts, methodology notes, and citation audit trail (ReportLab engine).",
                    format_tag="PDF",
                    icon="file-text",
                    on_click=AppState.generate_pdf,
                    variant="primary",
                ),
                report_card(
                    title="Editable Word Document",
                    description="Standard Microsoft Word document (.docx) formatted for executive markup, commentary, and board reviews (python-docx engine).",
                    format_tag="DOCX",
                    icon="file-spreadsheet",
                    on_click=AppState.generate_docx,
                    variant="secondary",
                ),
                columns=rx.breakpoints(initial="1", md="2"),
                spacing="3",
                width="100%",
            ),

            # 3. Past Generated Reports Repository
            neu_card(
                rx.vstack(
                    rx.hstack(
                        rx.hstack(
                            rx.icon(tag="archive", size=16, color=ACCENT_COLOR),
                            rx.text("Generated Reports Repository", font_size="1rem", font_weight="600", color=TEXT_COLOR),
                            spacing="2",
                            align_items="center",
                        ),
                        rx.spacer(),
                        neu_button(
                            rx.hstack(
                                rx.icon(tag="rotate-cw", size=12),
                                rx.text("Refresh"),
                                spacing="1",
                                align_items="center",
                            ),
                            variant="ghost",
                            on_click=AppState.fetch_reports,
                        ),
                        width="100%",
                        align_items="center",
                    ),
                    rx.text(
                        "Reports generated for this account are stored under data/reports/. Click download to open in your system viewer.",
                        font_size="0.8rem",
                        color=TEXT_MUTED,
                    ),
                    # Reports table or honest empty state
                    rx.cond(
                        AppState.past_reports.length() > 0,
                        neu_inset_card(
                            rx.table.root(
                                rx.table.header(
                                    rx.table.row(
                                        rx.table.column_header_cell("Filename"),
                                        rx.table.column_header_cell("Dataset"),
                                        rx.table.column_header_cell("Format"),
                                        rx.table.column_header_cell("Created"),
                                        rx.table.column_header_cell("Action"),
                                    )
                                ),
                                rx.table.body(
                                    rx.foreach(AppState.past_reports, past_report_row)
                                ),
                                width="100%",
                            ),
                            padding="0.5rem",
                            width="100%",
                            overflow_x="auto",
                        ),
                        empty_state(
                            title="No Generated Reports Yet",
                            description="Click either Export button above to generate publication-grade PDF or editable Word reports.",
                            icon="file-text",
                        ),
                    ),
                    spacing="3",
                    align_items="flex-start",
                    width="100%",
                ),
                width="100%",
            ),

            spacing="4",
            width="100%",
        ),
    )
