import reflex as rx
from frontend.components.layout import app_layout
from frontend.state import AppState

def chat_page() -> rx.Component:
    AppState.active_tab = "chat"
    return app_layout(
        "Autonomous Analyst Chat",
        rx.vstack(
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.box(
                            rx.icon(tag="message-square", size=20, color="#818cf8"),
                            padding="0.5rem",
                            border_radius="0.5rem",
                            background_color="rgba(99, 102, 241, 0.15)"
                        ),
                        rx.vstack(
                            rx.text("Conversational Data Exploration", font_weight="700", font_size="1.1rem", color="#ffffff"),
                            rx.text("Ask questions about the dataset; the agent re-invokes tools only when new computation is required.", font_size="0.8rem", color="#94a3b8"),
                            spacing="0",
                            align_items="flex-start"
                        ),
                        spacing="3",
                        align_items="center"
                    ),
                    rx.divider(border_color="rgba(255, 255, 255, 0.08)"),
                    rx.box(
                        rx.vstack(
                            rx.icon(tag="bot", size=40, color="#6366f1"),
                            rx.text("Chat Interface Ready for Agent Integration (Phase 2 & 3)", font_weight="600", color="#f1f5f9"),
                            rx.text("Connects to the Anthropic Claude API tool-calling loop and DuckDB ad-hoc querying in Phase 2.", font_size="0.85rem", color="#94a3b8"),
                            spacing="2",
                            align_items="center",
                            padding="4rem"
                        ),
                        background_color="rgba(15, 23, 42, 0.4)",
                        border="1px dashed rgba(255, 255, 255, 0.08)",
                        border_radius="0.65rem",
                        width="100%"
                    ),
                    # Chat input box
                    rx.hstack(
                        rx.input(
                            placeholder="e.g., 'What are the top factors correlated with employee attrition?'",
                            size="3",
                            width="100%",
                            variant="surface"
                        ),
                        rx.button(
                            rx.icon(tag="send", size=16),
                            size="3",
                            variant="solid",
                            color_scheme="indigo"
                        ),
                        spacing="3",
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
            spacing="5",
            width="100%"
        )
    )
