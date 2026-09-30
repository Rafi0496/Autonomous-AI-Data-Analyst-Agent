"""Interactive Chat Q&A Page for Autonomous AI Data Analyst Agent (Milestone 4)."""
import reflex as rx
from frontend.components.layout import app_layout
from frontend.state import AppState, ChatMessageModel, EvidenceItemModel

def render_message_bubble(msg: ChatMessageModel) -> rx.Component:
    """Render a single user or assistant chat message with evidence chips and verification."""
    is_user = msg.role == "user"
    return rx.box(
        rx.hstack(
            rx.cond(
                is_user,
                rx.spacer(),
                rx.box(
                    rx.icon(tag="bot", size=18, color="#818cf8"),
                    padding="0.4rem",
                    border_radius="50%",
                    background_color="rgba(99, 102, 241, 0.15)",
                    border="1px solid rgba(99, 102, 241, 0.3)"
                )
            ),
            rx.box(
                rx.vstack(
                    rx.hstack(
                        rx.text(
                            rx.cond(is_user, "You", "Autonomous Analyst"),
                            font_size="0.75rem",
                            font_weight="600",
                            color=rx.cond(is_user, "#93c5fd", "#c084fc")
                        ),
                        rx.spacer(),
                        rx.cond(
                            msg.role != "user",
                            rx.badge(
                                msg.verification_summary,
                                color_scheme=rx.cond(msg.verification_is_valid, "green", "amber"),
                                variant="surface",
                                size="1"
                            )
                        ),
                        width="100%",
                        align_items="center"
                    ),
                    rx.text(
                        msg.content,
                        font_size="0.875rem",
                        color="#f1f5f9",
                        line_height="1.5",
                        white_space="pre-wrap"
                    ),
                    # Evidence chips if assistant message has evidence
                    rx.cond(
                        msg.evidence.length() > 0,
                        rx.box(
                            rx.vstack(
                                rx.text("Evidence & Grounding:", font_size="0.7rem", font_weight="600", color="#94a3b8"),
                                rx.hstack(
                                    rx.foreach(
                                        msg.evidence,
                                        lambda ev: rx.badge(
                                            rx.hstack(
                                                rx.icon(tag="link", size=10),
                                                rx.text(ev.title, font_size="0.7rem"),
                                                spacing="1",
                                                align_items="center"
                                            ),
                                            color_scheme="indigo",
                                            variant="soft",
                                            size="1"
                                        )
                                    ),
                                    wrap="wrap",
                                    spacing="1"
                                ),
                                spacing="1",
                                align_items="flex-start",
                                width="100%"
                            ),
                            padding="0.5rem 0.75rem",
                            border_radius="0.375rem",
                            background_color="rgba(15, 23, 42, 0.4)",
                            border="1px solid rgba(255, 255, 255, 0.05)",
                            margin_top="0.5rem",
                            width="100%"
                        )
                    ),
                    spacing="2",
                    align_items="flex-start",
                    width="100%"
                ),
                padding="1rem 1.25rem",
                border_radius="0.75rem",
                background_color=rx.cond(
                    is_user,
                    "rgba(99, 102, 241, 0.15)",
                    "rgba(30, 41, 59, 0.6)"
                ),
                border=rx.cond(
                    is_user,
                    "1px solid rgba(99, 102, 241, 0.3)",
                    "1px solid rgba(255, 255, 255, 0.08)"
                ),
                max_width=rx.cond(is_user, "70%", "85%"),
                width="fit-content"
            ),
            rx.cond(
                is_user,
                rx.box(
                    rx.icon(tag="user", size=18, color="#60a5fa"),
                    padding="0.4rem",
                    border_radius="50%",
                    background_color="rgba(59, 130, 246, 0.15)",
                    border="1px solid rgba(59, 130, 246, 0.3)"
                ),
                rx.spacer()
            ),
            spacing="3",
            align_items="flex-start",
            width="100%"
        ),
        width="100%"
    )

def chat_page() -> rx.Component:
    AppState.active_tab = "chat"
    return app_layout(
        "Autonomous Analyst Chat",
        rx.vstack(
            rx.box(
                rx.vstack(
                    # Header
                    rx.hstack(
                        rx.box(
                            rx.icon(tag="message-square", size=20, color="#818cf8"),
                            padding="0.5rem",
                            border_radius="0.5rem",
                            background_color="rgba(99, 102, 241, 0.15)"
                        ),
                        rx.vstack(
                            rx.text("Conversational Data Exploration", font_weight="700", font_size="1.1rem", color="#ffffff"),
                            rx.text(
                                f"Active Dataset: {AppState.selected_dataset_name} | Ask analytical questions; tools re-invoked on-demand (max 3 calls).",
                                font_size="0.8rem",
                                color="#94a3b8"
                            ),
                            spacing="0",
                            align_items="flex-start"
                        ),
                        rx.spacer(),
                        rx.cond(
                            AppState.chat_messages.length() > 0,
                            rx.button(
                                rx.hstack(
                                    rx.icon(tag="trash-2", size=14),
                                    rx.text("Clear History"),
                                    spacing="1"
                                ),
                                size="1",
                                variant="ghost",
                                color_scheme="gray",
                                on_click=AppState.clear_chat
                            )
                        ),
                        spacing="3",
                        align_items="center",
                        width="100%"
                    ),
                    rx.divider(border_color="rgba(255, 255, 255, 0.08)"),

                    # Suggested Starter Questions Chips
                    rx.vstack(
                        rx.text("Suggested Analytical Questions:", font_size="0.75rem", font_weight="600", color="#94a3b8"),
                        rx.hstack(
                            rx.foreach(
                                AppState.suggested_questions,
                                lambda sq: rx.button(
                                    rx.hstack(
                                        rx.icon(tag="sparkles", size=12, color="#818cf8"),
                                        rx.text(sq, font_size="0.75rem"),
                                        spacing="1",
                                        align_items="center"
                                    ),
                                    size="1",
                                    variant="surface",
                                    color_scheme="indigo",
                                    on_click=AppState.ask_suggested(sq)
                                )
                            ),
                            wrap="wrap",
                            spacing="2"
                        ),
                        spacing="2",
                        align_items="flex-start",
                        width="100%"
                    ),

                    # Message Thread Box
                    rx.box(
                        rx.cond(
                            AppState.chat_messages.length() > 0,
                            rx.vstack(
                                rx.foreach(AppState.chat_messages, render_message_bubble),
                                rx.cond(
                                    AppState.is_chatting,
                                    rx.hstack(
                                        rx.spinner(size="2", color="#818cf8"),
                                        rx.text("Autonomous agent analyzing facts and citations...", font_size="0.8rem", color="#94a3b8"),
                                        spacing="2",
                                        align_items="center",
                                        padding="0.75rem"
                                    )
                                ),
                                spacing="4",
                                width="100%"
                            ),
                            rx.box(
                                rx.vstack(
                                    rx.icon(tag="bot", size=36, color="#6366f1"),
                                    rx.text("Ask Any Question About Your Data", font_weight="600", color="#f1f5f9"),
                                    rx.text(
                                        "Questions are grounded in dataset profiles, cleaning audits, and autonomous insights. Every numeric claim is verified.",
                                        font_size="0.8rem",
                                        color="#94a3b8",
                                        text_align="center",
                                        max_width="450px"
                                    ),
                                    spacing="2",
                                    align_items="center",
                                    justify_content="center",
                                    padding="3rem 1.5rem"
                                ),
                                width="100%"
                            )
                        ),
                        min_height="350px",
                        max_height="500px",
                        overflow_y="auto",
                        padding="1.25rem",
                        border_radius="0.65rem",
                        background_color="rgba(15, 23, 42, 0.4)",
                        border="1px solid rgba(255, 255, 255, 0.06)",
                        width="100%"
                    ),

                    # Chat Input Bar
                    rx.hstack(
                        rx.input(
                            placeholder="Ask a question (e.g., 'What were the top anomalies and clean rows count?')",
                            value=AppState.chat_input,
                            on_change=AppState.set_chat_input,
                            size="3",
                            width="100%",
                            variant="surface"
                        ),
                        rx.button(
                            rx.cond(
                                AppState.is_chatting,
                                rx.spinner(size="1"),
                                rx.hstack(
                                    rx.icon(tag="send", size=15),
                                    rx.text("Send"),
                                    spacing="1"
                                )
                            ),
                            size="3",
                            variant="solid",
                            color_scheme="indigo",
                            is_loading=AppState.is_chatting,
                            on_click=AppState.send_chat_message
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
