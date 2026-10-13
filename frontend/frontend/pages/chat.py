"""Interactive Follow-up Chat Q&A page for Autonomous AI Data Analyst Agent.
Neo-morphism 60% + Minimalism 40% with sunken thread, raised assistant responses,
grounded citation chips, verification badges, and pinned slate-teal input bar.
"""
from typing import Any, Dict
import reflex as rx
from frontend.components.layout import app_layout
from frontend.components.neu_components import (
    citation_chip,
    empty_state,
    neu_button,
    neu_card,
    neu_icon_button,
    neu_input,
    neu_inset_card,
    status_pill,
)
from frontend.state import AppState, ChatMessageModel, EvidenceItemModel
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


def render_message_bubble(msg: ChatMessageModel) -> rx.Component:
    """Render a single user (inset sunken) or assistant (raised surface) message."""
    is_user = msg.role == "user"

    return rx.box(
        rx.hstack(
            # Left spacer for user messages
            rx.cond(
                is_user,
                rx.spacer(),
                # Assistant Avatar
                rx.box(
                    rx.icon(tag="bot", size=16, color=ACCENT_COLOR),
                    padding="0.45rem",
                    border_radius=RADIUS_FULL,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_RAISED_SM,
                    flex_shrink=0,
                ),
            ),

            # Message Bubble
            rx.box(
                rx.vstack(
                    # Header: sender name + verification badge
                    rx.hstack(
                        rx.text(
                            rx.cond(is_user, "You", "Autonomous Analyst"),
                            font_size="0.75rem",
                            font_weight="600",
                            color=rx.cond(is_user, ACCENT_COLOR, TEXT_COLOR),
                        ),
                        rx.spacer(),
                        rx.cond(
                            msg.role != "user",
                            status_pill(
                                msg.verification_summary,
                                icon="shield-check",
                                status=rx.cond(msg.verification_is_valid, "success", "warn"),
                            ),
                        ),
                        width="100%",
                        align_items="center",
                    ),

                    # Message content
                    rx.text(
                        msg.content,
                        font_size="0.85rem",
                        color=TEXT_COLOR,
                        line_height="1.55",
                        white_space="pre-wrap",
                    ),

                    # Retry Action if error
                    rx.cond(
                        msg.verification_summary == "Retryable",
                        neu_button(
                            rx.hstack(
                                rx.icon(tag="rotate-cw", size=12),
                                rx.text("Retry question", font_size="0.75rem"),
                                spacing="1",
                                align_items="center",
                            ),
                            variant="secondary",
                            size="1",
                            on_click=AppState.retry_last_chat_message,
                            margin_top="0.35rem",
                        ),
                    ),

                    # Evidence / Grounding Citation Chips
                    rx.cond(
                        msg.evidence.length() > 0,
                        rx.vstack(
                            rx.text("Grounding Citations & Tool Calls:", font_size="0.7rem", font_weight="600", color=TEXT_MUTED),
                            rx.hstack(
                                rx.foreach(
                                    msg.evidence,
                                    lambda ev: citation_chip(
                                        metric_key=ev.title,
                                        value=ev.tool,
                                    ),
                                ),
                                wrap="wrap",
                                spacing="1",
                                width="100%",
                            ),
                            spacing="1",
                            align_items="flex-start",
                            width="100%",
                            margin_top="0.4rem",
                        ),
                    ),

                    spacing="2",
                    align_items="flex-start",
                    width="100%",
                ),
                padding="1rem 1.15rem",
                border_radius=RADIUS_LG,
                background_color=SURFACE_COLOR,
                box_shadow=rx.cond(is_user, SHADOW_INSET, SHADOW_RAISED),
                max_width=rx.cond(is_user, "75%", "85%"),
                width="fit-content",
            ),

            # Right avatar for user
            rx.cond(
                is_user,
                rx.box(
                    rx.text(AppState.user_initial, font_size="0.75rem", font_weight="700", color="#ffffff"),
                    width="28px",
                    height="28px",
                    border_radius=RADIUS_FULL,
                    background_color=ACCENT_COLOR,
                    box_shadow=SHADOW_RAISED_SM,
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    flex_shrink=0,
                ),
                rx.spacer(),
            ),

            spacing="3",
            align_items="flex-start",
            width="100%",
        ),
        width="100%",
        padding_y="0.35rem",
    )


def chat_page() -> rx.Component:
    """Conversational data exploration screen."""
    return app_layout(
        "Chat",
        rx.vstack(
            neu_card(
                rx.vstack(
                    # 1. Header Row
                    rx.hstack(
                        rx.hstack(
                            rx.box(
                                rx.icon(tag="message-square", size=18, color=ACCENT_COLOR),
                                padding="0.55rem",
                                border_radius=RADIUS_FULL,
                                background_color=SURFACE_COLOR,
                                box_shadow=SHADOW_INSET,
                            ),
                            rx.vstack(
                                rx.text("Conversational Data Exploration", font_size="1.05rem", font_weight="600", color=TEXT_COLOR),
                                rx.text(
                                    "Factual statistical grounding with multi-phase verification.",
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
                        # Dataset selector in header, defaulting to most recent ready dataset
                        rx.hstack(
                            rx.icon(tag="database", size=14, color=TEXT_MUTED),
                            rx.select(
                                items=AppState.dataset_options,
                                value=AppState.selected_dataset_name,
                                on_change=AppState.select_dataset_by_name,
                                placeholder="Select dataset...",
                                size="1",
                                variant="surface",
                            ),
                            spacing="2",
                            align_items="center",
                        ),
                        rx.cond(
                            AppState.chat_messages.length() > 0,
                            neu_button(
                                rx.hstack(
                                    rx.icon(tag="trash-2", size=13),
                                    rx.text("Clear"),
                                    spacing="1",
                                    align_items="center",
                                ),
                                variant="ghost",
                                on_click=AppState.clear_chat,
                            ),
                        ),
                        width="100%",
                        align_items="center",
                    ),

                    # 2. Suggested Starter Questions Chips
                    rx.vstack(
                        rx.text("Suggested Follow-up Inquiries:", font_size="0.75rem", font_weight="600", color=TEXT_MUTED),
                        rx.hstack(
                            rx.foreach(
                                AppState.suggested_questions,
                                lambda sq: rx.box(
                                    rx.hstack(
                                        rx.icon(tag="sparkles", size=12, color=ACCENT_COLOR),
                                        rx.text(sq, font_size="0.75rem", color=TEXT_COLOR),
                                        spacing="1",
                                        align_items="center",
                                    ),
                                    background_color=SURFACE_COLOR,
                                    box_shadow=SHADOW_RAISED_SM,
                                    border_radius=RADIUS_MD,
                                    padding="0.35rem 0.75rem",
                                    cursor="pointer",
                                    on_click=AppState.ask_suggested(sq),
                                    _hover={"box_shadow": SHADOW_INSET},
                                    transition="box-shadow 150ms ease",
                                ),
                            ),
                            wrap="wrap",
                            spacing="2",
                            width="100%",
                        ),
                        spacing="2",
                        align_items="flex-start",
                        width="100%",
                    ),

                    # 3. Message Thread Inset Container
                    neu_inset_card(
                        rx.vstack(
                            rx.cond(
                                AppState.chat_messages.length() > 0,
                                rx.vstack(
                                    rx.foreach(AppState.chat_messages, render_message_bubble),
                                    # Typing indicator with pulsing animation
                                    rx.cond(
                                        AppState.is_chatting,
                                        rx.box(
                                            rx.hstack(
                                                rx.box(
                                                    rx.icon(tag="bot", size=16, color=ACCENT_COLOR),
                                                    padding="0.45rem",
                                                    border_radius=RADIUS_FULL,
                                                    background_color=SURFACE_COLOR,
                                                    box_shadow=SHADOW_RAISED_SM,
                                                ),
                                                rx.box(
                                                    rx.hstack(
                                                        rx.box(width="7px", height="7px", border_radius=RADIUS_FULL, background_color=ACCENT_COLOR, class_name="neu-pulse-dot-1"),
                                                        rx.box(width="7px", height="7px", border_radius=RADIUS_FULL, background_color=ACCENT_COLOR, class_name="neu-pulse-dot-2"),
                                                        rx.box(width="7px", height="7px", border_radius=RADIUS_FULL, background_color=ACCENT_COLOR, class_name="neu-pulse-dot-3"),
                                                        rx.text("Autonomous agent querying facts...", font_size="0.8rem", color=TEXT_MUTED, font_style="italic"),
                                                        spacing="2",
                                                        align_items="center",
                                                    ),
                                                    padding="0.75rem 1.15rem",
                                                    border_radius=RADIUS_LG,
                                                    background_color=SURFACE_COLOR,
                                                    box_shadow=SHADOW_RAISED,
                                                ),
                                                spacing="3",
                                                align_items="center",
                                            ),
                                            width="100%",
                                            padding_y="0.35rem",
                                        ),
                                    ),
                                    spacing="2",
                                    width="100%",
                                ),
                                # Honest empty conversation state
                                rx.vstack(
                                    rx.box(
                                        rx.icon(tag="bot", size=28, color=TEXT_MUTED),
                                        padding="0.85rem",
                                        border_radius=RADIUS_FULL,
                                        background_color=SURFACE_COLOR,
                                        box_shadow=SHADOW_RAISED_SM,
                                    ),
                                    rx.text("Ask Any Question About Your Data", font_size="0.95rem", font_weight="600", color=TEXT_COLOR),
                                    rx.text(
                                        "Queries are answered strictly using computed facts, database SQL queries, and correlation profiles. "
                                        "You can also chat freely without a dataset selected.",
                                        font_size="0.8rem",
                                        color=TEXT_MUTED,
                                        text_align="center",
                                        max_width="440px",
                                        line_height="1.5",
                                    ),
                                    spacing="2",
                                    align_items="center",
                                    justify_content="center",
                                    padding_y="3.5rem",
                                    width="100%",
                                ),
                            ),
                            width="100%",
                        ),
                        id="chat-thread-container",
                        min_height="380px",
                        max_height="520px",
                        overflow_y="auto",
                        padding="1.25rem",
                        width="100%",
                    ),

                    # 4. Pinned Bottom Input Bar (Twin of Hero Input with Enter to send)
                    neu_inset_card(
                        rx.hstack(
                            rx.icon(tag="terminal", size=16, color=TEXT_MUTED),
                            rx.text_area(
                                id="chat-input-textarea",
                                placeholder="Ask a question grounded in computed facts... (Enter sends, Shift+Enter for newline)",
                                value=AppState.chat_input,
                                on_change=AppState.set_chat_input,
                                on_key_down=AppState.handle_chat_key_down,
                                border="none",
                                background="transparent",
                                color=TEXT_COLOR,
                                font_size="0.875rem",
                                outline="none",
                                width="100%",
                                rows="1",
                                resize="none",
                                class_name="neu-input-field",
                                _focus={"outline": "none"},
                            ),
                            neu_button(
                                rx.cond(
                                    AppState.is_chatting,
                                    rx.icon(tag="loader", size=14, class_name="neu-active-step-pulse"),
                                    rx.hstack(
                                        rx.icon(tag="arrow-up", size=14),
                                        spacing="1",
                                        align_items="center",
                                    ),
                                ),
                                variant="primary",
                                is_loading=AppState.is_chatting,
                                is_disabled=AppState.is_chatting,
                                on_click=AppState.send_chat_message,
                                padding="0.55rem 0.85rem",
                                border_radius=RADIUS_FULL,
                            ),
                            spacing="2",
                            align_items="center",
                            width="100%",
                        ),
                        class_name="neu-input-container",
                        padding="0.5rem 0.85rem",
                        border_radius=RADIUS_XL,
                        width="100%",
                    ),

                    spacing="4",
                    align_items="flex-start",
                    width="100%",
                ),
                width="100%",
            ),
            spacing="4",
            width="100%",
        ),
    )
