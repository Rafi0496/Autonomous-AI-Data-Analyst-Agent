import reflex as rx
from frontend.components.layout import app_layout
from frontend.state import AppState

def report_type_card(title: str, format_name: str, desc: str, icon_name: str, badge_text: str) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(tag=icon_name, size=24, color="#818cf8"),
                rx.vstack(
                    rx.text(title, font_weight="600", font_size="1rem", color="#ffffff"),
                    rx.text(desc, font_size="0.8rem", color="#94a3b8"),
                    spacing="0",
                    align_items="flex-start"
                ),
                rx.spacer(),
                rx.badge(badge_text, color_scheme="indigo"),
                width="100%",
                align_items="center"
            ),
            rx.divider(border_color="rgba(255, 255, 255, 0.08)"),
            rx.button(
                rx.hstack(
                    rx.icon(tag="file-down", size=16),
                    rx.text(f"Export as {format_name}"),
                    spacing="2",
                    align_items="center"
                ),
                size="2",
                variant="surface",
                color_scheme="indigo",
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
    )

def reports_page() -> rx.Component:
    AppState.active_tab = "reports"
    return app_layout(
        "Report Generation & Export",
        rx.vstack(
            rx.box(
                rx.vstack(
                    rx.text("Export Business Intelligence Reports", font_size="1.1rem", font_weight="700", color="#ffffff"),
                    rx.text(
                        "Generates publication-ready business briefs containing the executive summary, "
                        "ranked findings, embedded visualizations, and methodology appendix per PRD FR-17.",
                        font_size="0.85rem",
                        color="#94a3b8"
                    ),
                    spacing="1",
                    align_items="flex-start"
                ),
                padding="1.5rem",
                border_radius="0.75rem",
                background_color="rgba(15, 23, 42, 0.6)",
                border="1px solid rgba(255, 255, 255, 0.08)",
                width="100%"
            ),
            
            rx.grid(
                report_type_card(
                    "Executive Summary PDF",
                    "PDF",
                    "Styled presentation-grade report with charts & methodology (ReportLab / WeasyPrint).",
                    "file-text",
                    "PRD FR-17 Required"
                ),
                report_type_card(
                    "Editable Word Document",
                    "DOCX",
                    "Editable Microsoft Word document for stakeholder reviews (python-docx).",
                    "file-spreadsheet",
                    "PRD FR-17 Required"
                ),
                columns=rx.breakpoints(initial="1", md="2"),
                spacing="4",
                width="100%"
            ),
            spacing="5",
            width="100%"
        )
    )
