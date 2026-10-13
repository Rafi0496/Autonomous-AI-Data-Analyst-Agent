"""Home / New Analysis Screen: Serif greeting, large inset hero input, and recent runs row."""
from typing import Any, Dict
import reflex as rx
from frontend.components.layout import app_layout
from frontend.components.neu_components import (
    empty_state,
    hero_input,
    neu_button,
    neu_card,
    status_pill,
)
from frontend.state import AppState, RecentJobModel
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


def recent_analysis_card(job: RecentJobModel) -> rx.Component:
    """Row item: Raised card showing a recent analytical run."""
    status_color = rx.cond(
        job.status == "completed",
        "var(--status-success)",
        rx.cond(job.status == "failed", "var(--status-error)", "var(--status-warning)"),
    )

    return rx.link(
        neu_card(
            rx.vstack(
                # Top: Dataset name & Status dot
                rx.hstack(
                    rx.box(
                        width="8px",
                        height="8px",
                        border_radius=RADIUS_FULL,
                        background_color=status_color,
                        flex_shrink=0,
                    ),
                    rx.text(
                        job.dataset_name,
                        font_size="0.85rem",
                        font_weight="600",
                        color=TEXT_COLOR,
                        is_truncated=True,
                    ),
                    rx.spacer(),
                    rx.icon(tag="arrow-up-right", size=14, color=TEXT_MUTED),
                    spacing="2",
                    align_items="center",
                    width="100%",
                ),
                # Goal description
                rx.text(
                    job.goal,
                    font_size="0.775rem",
                    color=TEXT_MUTED,
                    line_height="1.4",
                    is_truncated=True,
                    max_width="100%",
                ),
                # Bottom: Time group tag & status
                rx.hstack(
                    rx.text(
                        job.time_group,
                        font_size="0.7rem",
                        color=TEXT_MUTED,
                    ),
                    rx.spacer(),
                    rx.text(
                        job.status,
                        font_size="0.7rem",
                        font_weight="500",
                        color=TEXT_COLOR,
                    ),
                    width="100%",
                    align_items="center",
                ),
                spacing="2",
                align_items="flex-start",
                width="100%",
            ),
            sm=True,
            width="100%",
            cursor="pointer",
        ),
        href="/dashboard",
        text_decoration="none",
        width="100%",
    )


def home_page() -> rx.Component:
    """Home / New Analysis Screen."""
    return app_layout(
        "New Analysis",
        rx.vstack(
            # 1. Hero Brand Mark & Serif Greeting
            rx.vstack(
                rx.box(
                    rx.icon(tag="sparkles", size=24, color=ACCENT_COLOR),
                    padding="0.85rem",
                    border_radius=RADIUS_FULL,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_RAISED_SM,
                    display="inline-flex",
                    align_items="center",
                    justify_content="center",
                ),
                rx.text(
                    AppState.greeting_message,
                    font_family=FONT_SERIF,
                    font_size=rx.breakpoints(initial="2rem", sm="2.4rem"),
                    font_weight="400",
                    color=TEXT_COLOR,
                    letter_spacing="-0.02em",
                    text_align="center",
                    line_height="1.2",
                ),
                rx.text(
                    "Autonomous data ingestion, deterministic cleaning & grounded analytical synthesis.",
                    font_size="0.9rem",
                    color=TEXT_MUTED,
                    text_align="center",
                    max_width="520px",
                    line_height="1.5",
                ),
                spacing="3",
                align_items="center",
                width="100%",
                padding_y="2.5rem",
            ),

            # 2. Hero Input Container (Visual twin of chat box)
            rx.box(
                hero_input(
                    input_value=AppState.hero_prompt,
                    on_change=AppState.set_hero_prompt,
                    on_submit=AppState.handle_hero_submit,
                    on_key_down=AppState.handle_hero_key_down,
                    dataset_options=AppState.dataset_options,
                    selected_dataset=AppState.selected_dataset_name,
                    on_select_dataset=AppState.select_dataset_by_name,
                    on_attach_file=AppState.go_to_upload,
                    is_loading=AppState.is_analyzing,
                    placeholder="Ask an analytical question or describe your dataset... (Enter sends)",
                ),
                width="100%",
                max_width="780px",
                margin_x="auto",
            ),

            # Error Callout (if any)
            rx.cond(
                AppState.error_message != "",
                rx.callout(
                    AppState.error_message,
                    icon="circle-alert",
                    color_scheme="red",
                    size="1",
                    width="100%",
                    max_width="780px",
                    margin_top="1rem",
                ),
            ),

            # Status Message (if any)
            rx.cond(
                AppState.status_message != "",
                rx.callout(
                    AppState.status_message,
                    icon="info",
                    color_scheme="gray",
                    size="1",
                    width="100%",
                    max_width="780px",
                    margin_top="0.5rem",
                ),
            ),

            # 3. Row of 3 Recent Analyses as Raised Cards
            rx.vstack(
                rx.hstack(
                    rx.text(
                        "RECENT ANALYSES",
                        font_size="0.75rem",
                        font_weight="700",
                        color=TEXT_MUTED,
                        letter_spacing="0.08em",
                    ),
                    rx.spacer(),
                    rx.link(
                        rx.hstack(
                            rx.text("View all", font_size="0.75rem", color=ACCENT_COLOR, font_weight="500"),
                            rx.icon(tag="chevron-right", size=13, color=ACCENT_COLOR),
                            spacing="1",
                            align_items="center",
                        ),
                        href="/dashboard",
                        text_decoration="none",
                    ),
                    width="100%",
                    align_items="center",
                    padding_x="0.25rem",
                ),
                # If there are recent runs: render 3-column grid
                rx.cond(
                    AppState.top_recent_jobs.length() > 0,
                    rx.grid(
                        rx.foreach(
                            AppState.top_recent_jobs,
                            lambda job: recent_analysis_card(job),
                        ),
                        columns=rx.breakpoints(initial="1", sm="3"),
                        spacing="3",
                        width="100%",
                    ),
                    empty_state(
                        title="No Analyses Yet",
                        description="Upload a CSV or select a benchmark dataset above to trigger an autonomous analysis run.",
                        icon="sparkles",
                        action_button=neu_button(
                            "Upload Dataset",
                            variant="secondary",
                            on_click=AppState.go_to_upload,
                        ),
                    ),
                ),
                spacing="3",
                width="100%",
                max_width="780px",
                margin_top="2.5rem",
            ),
            spacing="0",
            align_items="center",
            width="100%",
        ),
        max_width="820px",
    )
