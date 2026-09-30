"""Interactive Report Generation and Export page for Autonomous AI Data Analyst Agent (Milestone 5)."""
import reflex as rx
from frontend.components.layout import app_layout
from frontend.state import AppState, ReportItemModel

def reports_page() -> rx.Component:
    AppState.active_tab = "reports"
    return app_layout(
        "Report Generation & Export",
        rx.vstack(
            # Header info card
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.box(
                            rx.icon(tag="file-text", size=20, color="#818cf8"),
                            padding="0.5rem",
                            border_radius="0.5rem",
                            background_color="rgba(99, 102, 241, 0.15)"
                        ),
                        rx.vstack(
                            rx.text("Export Business Intelligence Reports", font_size="1.1rem", font_weight="700", color="#ffffff"),
                            rx.text(
                                f"Active Dataset: {AppState.selected_dataset_name} | Generates publication-ready PDF and Word reports with charts, executive summary, and methodology audit trail.",
                                font_size="0.8rem",
                                color="#94a3b8"
                            ),
                            spacing="0",
                            align_items="flex-start"
                        ),
                        rx.spacer(),
                        rx.cond(
                            AppState.active_job_id != "",
                            rx.badge(f"Job: {AppState.active_job_id[:8]}", color_scheme="indigo", variant="surface"),
                            rx.badge("No active analysis job", color_scheme="gray", variant="soft")
                        ),
                        spacing="3",
                        align_items="center",
                        width="100%"
                    ),
                    spacing="2",
                    align_items="flex-start"
                ),
                padding="1.5rem",
                border_radius="0.75rem",
                background_color="rgba(15, 23, 42, 0.6)",
                border="1px solid rgba(255, 255, 255, 0.08)",
                width="100%"
            ),

            # Generation Cards Grid
            rx.grid(
                # PDF Generation Card
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="file-text", size=24, color="#ef4444"),
                            rx.vstack(
                                rx.text("Executive Summary PDF", font_weight="700", font_size="1rem", color="#ffffff"),
                                rx.text("Styled presentation-grade report with charts & methodology (ReportLab).", font_size="0.8rem", color="#94a3b8"),
                                spacing="0",
                                align_items="flex-start"
                            ),
                            rx.spacer(),
                            rx.badge("PDF", color_scheme="red", variant="surface"),
                            width="100%",
                            align_items="center"
                        ),
                        rx.divider(border_color="rgba(255, 255, 255, 0.08)"),
                        rx.button(
                            rx.hstack(
                                rx.icon(tag="file-down", size=16),
                                rx.text("Generate & Export PDF"),
                                spacing="2",
                                align_items="center"
                            ),
                            size="3",
                            variant="solid",
                            color_scheme="indigo",
                            width="100%",
                            is_loading=AppState.is_generating_report,
                            on_click=AppState.generate_pdf
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
                ),

                # DOCX Generation Card
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="file-spreadsheet", size=24, color="#3b82f6"),
                            rx.vstack(
                                rx.text("Editable Word Document", font_weight="700", font_size="1rem", color="#ffffff"),
                                rx.text("Editable Microsoft Word document for stakeholder review (python-docx).", font_size="0.8rem", color="#94a3b8"),
                                spacing="0",
                                align_items="flex-start"
                            ),
                            rx.spacer(),
                            rx.badge("DOCX", color_scheme="blue", variant="surface"),
                            width="100%",
                            align_items="center"
                        ),
                        rx.divider(border_color="rgba(255, 255, 255, 0.08)"),
                        rx.button(
                            rx.hstack(
                                rx.icon(tag="file-down", size=16),
                                rx.text("Generate & Export Word (.docx)"),
                                spacing="2",
                                align_items="center"
                            ),
                            size="3",
                            variant="solid",
                            color_scheme="blue",
                            width="100%",
                            is_loading=AppState.is_generating_report,
                            on_click=AppState.generate_docx
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
                ),
                columns=rx.breakpoints(initial="1", md="2"),
                spacing="4",
                width="100%"
            ),

            # Past Generated Reports Table
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.hstack(
                            rx.icon(tag="history", size=18, color="#818cf8"),
                            rx.text("Generated Reports Repository", font_weight="700", font_size="1rem", color="#ffffff"),
                            spacing="2",
                            align_items="center"
                        ),
                        rx.spacer(),
                        rx.button(
                            rx.hstack(
                                rx.icon(tag="refresh-cw", size=14),
                                rx.text("Refresh"),
                                spacing="1"
                            ),
                            size="1",
                            variant="ghost",
                            color_scheme="gray",
                            on_click=AppState.fetch_reports
                        ),
                        spacing="3",
                        align_items="center",
                        width="100%"
                    ),
                    rx.text("Stored locally under data/reports/. Click download to open with your local PDF or Word viewer.", font_size="0.8rem", color="#94a3b8"),
                    rx.cond(
                        AppState.past_reports.length() > 0,
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Filename"),
                                    rx.table.column_header_cell("Dataset"),
                                    rx.table.column_header_cell("Format"),
                                    rx.table.column_header_cell("Created"),
                                    rx.table.column_header_cell("Action")
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    AppState.past_reports,
                                    lambda rep: rx.table.row(
                                        rx.table.cell(rx.text(rep.filename, font_weight="600", color="#f1f5f9")),
                                        rx.table.cell(rx.text(rep.dataset_name, font_size="0.8rem", color="#94a3b8")),
                                        rx.table.cell(
                                            rx.badge(
                                                rep.format.upper(),
                                                color_scheme=rx.cond(rep.format == "pdf", "red", "blue"),
                                                variant="solid",
                                                size="1"
                                            )
                                        ),
                                        rx.table.cell(rx.text(rep.created_at, font_size="0.75rem", color="#64748b")),
                                        rx.table.cell(
                                            rx.link(
                                                rx.button(
                                                    rx.hstack(
                                                        rx.icon(tag="download", size=12),
                                                        rx.text("Download"),
                                                        spacing="1"
                                                    ),
                                                    size="1",
                                                    variant="soft",
                                                    color_scheme="indigo"
                                                ),
                                                href=f"http://127.0.0.1:8000{rep.download_url}",
                                                is_external=True
                                            )
                                        )
                                    )
                                )
                            ),
                            variant="surface",
                            width="100%"
                        ),
                        rx.box(
                            rx.text("No generated reports yet. Click either Export button above to generate a report.", font_size="0.85rem", color="#64748b", text_align="center", padding="2rem"),
                            width="100%"
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
            ),

            spacing="5",
            width="100%"
        )
    )
