"""System Configuration & Settings page for Autonomous AI Data Analyst Agent.
Neo-morphism 60% + Minimalism 40% with user profile session, theme mode switcher,
and verified backend orchestration parameters.
"""
from typing import Any, Dict
import reflex as rx
from frontend.components.layout import app_layout
from frontend.components.neu_components import (
    neu_button,
    neu_card,
    neu_inset_card,
    status_pill,
)
from frontend.state import AppState
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


def config_item(title: str, badge_text: Any, description: str, icon: str) -> rx.Component:
    """Card item displaying an active runtime parameter."""
    return neu_card(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon(tag=icon, size=15, color=ACCENT_COLOR),
                    padding="0.45rem",
                    border_radius=RADIUS_FULL,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_INSET,
                ),
                rx.text(title, font_size="0.825rem", font_weight="600", color=TEXT_COLOR),
                rx.spacer(),
                rx.box(
                    rx.text(badge_text, font_size="0.75rem", font_weight="700", color=ACCENT_COLOR),
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_INSET,
                    padding="0.2rem 0.55rem",
                    border_radius=RADIUS_SM,
                ),
                spacing="2",
                align_items="center",
                width="100%",
            ),
            rx.text(description, font_size="0.78rem", color=TEXT_MUTED, line_height="1.45"),
            spacing="2",
            align_items="flex-start",
            width="100%",
        ),
        sm=True,
        width="100%",
    )


def settings_page() -> rx.Component:
    """Settings & System Parameters page."""
    return app_layout(
        "Settings",
        rx.vstack(
            # 1. User Profile & Session Card
            neu_card(
                rx.vstack(
                    rx.hstack(
                        rx.hstack(
                            rx.box(
                                rx.text(AppState.user_initial, font_weight="700", font_size="1rem", color="#ffffff"),
                                width="40px",
                                height="40px",
                                border_radius=RADIUS_FULL,
                                background_color=ACCENT_COLOR,
                                box_shadow=SHADOW_RAISED_SM,
                                display="flex",
                                align_items="center",
                                justify_content="center",
                            ),
                            rx.vstack(
                                rx.text(
                                    rx.cond(AppState.is_authenticated, AppState.current_user_name, "Guest User"),
                                    font_size="1.05rem",
                                    font_weight="600",
                                    color=TEXT_COLOR,
                                ),
                                rx.text(
                                    rx.cond(AppState.is_authenticated, AppState.current_user_email, "Guest workspace (Local session)"),
                                    font_size="0.8rem",
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
                            AppState.is_authenticated,
                            neu_button(
                                rx.hstack(
                                    rx.icon(tag="log-out", size=14),
                                    rx.text("Sign Out"),
                                    spacing="1",
                                    align_items="center",
                                ),
                                variant="secondary",
                                on_click=AppState.logout,
                            ),
                            neu_button(
                                rx.hstack(
                                    rx.icon(tag="log-in", size=14),
                                    rx.text("Sign In / Register"),
                                    spacing="1",
                                    align_items="center",
                                ),
                                variant="primary",
                                on_click=AppState.toggle_auth_dialog,
                            ),
                        ),
                        width="100%",
                        align_items="center",
                    ),
                    spacing="3",
                    align_items="flex-start",
                    width="100%",
                ),
                width="100%",
            ),

            # 2. Appearance & Interface Theme
            neu_card(
                rx.vstack(
                    rx.hstack(
                        rx.box(
                            rx.icon(tag="palette", size=16, color=ACCENT_COLOR),
                            padding="0.5rem",
                            border_radius=RADIUS_FULL,
                            background_color=SURFACE_COLOR,
                            box_shadow=SHADOW_INSET,
                        ),
                        rx.vstack(
                            rx.text("Visual Theme & Aesthetics", font_size="0.95rem", font_weight="600", color=TEXT_COLOR),
                            rx.text("Neo-morphism 60% + Minimalism 40% with dual tonal shadows and slate-teal accent.", font_size="0.78rem", color=TEXT_MUTED),
                            spacing="0",
                            align_items="flex-start",
                        ),
                        rx.spacer(),
                        # Toggle Switch between dark and light
                        neu_button(
                            rx.hstack(
                                rx.icon(
                                    tag=rx.cond(AppState.theme_mode == "dark", "moon", "sun"),
                                    size=14,
                                    color=ACCENT_COLOR,
                                ),
                                rx.text(
                                    rx.cond(AppState.theme_mode == "dark", "Dark Mode", "Light Mode"),
                                    font_size="0.8rem",
                                    color=TEXT_COLOR,
                                ),
                                spacing="2",
                                align_items="center",
                            ),
                            variant="secondary",
                            on_click=[rx.call_script("window.__toggleThemeInstant?.();"), AppState.toggle_theme],
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

            # 3. Active Backend Orchestration Parameters (Neutral, zero provider names)
            neu_card(
                rx.vstack(
                    rx.hstack(
                        rx.hstack(
                            rx.box(
                                rx.icon(tag="sliders-horizontal", size=16, color=ACCENT_COLOR),
                                padding="0.5rem",
                                border_radius=RADIUS_FULL,
                                background_color=SURFACE_COLOR,
                                box_shadow=SHADOW_INSET,
                            ),
                            rx.vstack(
                                rx.text("Active Orchestration Parameters", font_size="1rem", font_weight="600", color=TEXT_COLOR),
                                rx.text("Verified against backend orchestration environment and execution guardrails.", font_size="0.78rem", color=TEXT_MUTED),
                                spacing="0",
                                align_items="flex-start",
                            ),
                            spacing="3",
                            align_items="center",
                        ),
                        width="100%",
                        align_items="center",
                    ),

                    # Grid of verified parameters
                    rx.grid(
                        config_item(
                            title="Analytics Engine",
                            badge_text="Autonomous",
                            description="Multi-phase autonomous reasoning engine for exploratory data analysis.",
                            icon="bot",
                        ),
                        config_item(
                            title="Execution Pipeline",
                            badge_text="Active",
                            description="Perceive-plan-act-reflect-synthesize analytical cycle with grounded citations.",
                            icon="cpu",
                        ),
                        config_item(
                            title="Step Limit Cap",
                            badge_text=f"{AppState.step_budget_setting} Steps",
                            description="Maximum Plan-Act-Reflect cycles allowed per analysis job before concluding.",
                            icon="layers",
                        ),
                        config_item(
                            title="Token Safety Cap",
                            badge_text=f"{AppState.token_budget_setting} Tokens",
                            description="Hard spending guardrail. If reached, job completes with verified deterministic synthesis.",
                            icon="coins",
                        ),
                        columns=rx.breakpoints(initial="1", sm="2"),
                        spacing="3",
                        width="100%",
                    ),
                    spacing="3",
                    align_items="flex-start",
                    width="100%",
                ),
                width="100%",
            ),

            # 4. Verified Stack Architecture
            neu_card(
                rx.vstack(
                    rx.hstack(
                        rx.icon(tag="boxes", size=16, color=ACCENT_COLOR),
                        rx.text("System Architecture & Verification", font_size="0.95rem", font_weight="600", color=TEXT_COLOR),
                        spacing="2",
                        align_items="center",
                    ),
                    rx.grid(
                        neu_inset_card(
                            rx.vstack(
                                rx.text("Core API Backend", font_size="0.75rem", font_weight="600", color=TEXT_COLOR),
                                rx.text("FastAPI + Celery asynchronous task queue with SQLite/Postgres persistence.", font_size="0.72rem", color=TEXT_MUTED),
                                spacing="1",
                            ),
                            padding="0.7rem 0.85rem",
                        ),
                        neu_inset_card(
                            rx.vstack(
                                rx.text("Reflex Frontend", font_size="0.75rem", font_weight="600", color=TEXT_COLOR),
                                rx.text("Pure Python fullstack framework with real-time reactive event loops and LocalStorage auth.", font_size="0.72rem", color=TEXT_MUTED),
                                spacing="1",
                            ),
                            padding="0.7rem 0.85rem",
                        ),
                        neu_inset_card(
                            rx.vstack(
                                rx.text("Grounded Reporting", font_size="0.75rem", font_weight="600", color=TEXT_COLOR),
                                rx.text("ReportLab (PDF) & python-docx (Word) headless generators with strict citation audits.", font_size="0.72rem", color=TEXT_MUTED),
                                spacing="1",
                            ),
                            padding="0.7rem 0.85rem",
                        ),
                        neu_inset_card(
                            rx.vstack(
                                rx.text("Statistical Analytics", font_size="0.75rem", font_weight="600", color=TEXT_COLOR),
                                rx.text("Pandas, NumPy & SciPy for deterministic profiling, segment tests, and effect sizes.", font_size="0.72rem", color=TEXT_MUTED),
                                spacing="1",
                            ),
                            padding="0.7rem 0.85rem",
                        ),
                        columns=rx.breakpoints(initial="1", sm="2"),
                        spacing="3",
                        width="100%",
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
