"""App Layout Shell with Neumorphic 60% + Minimalist 40% design, fixed sidebar, and centered column."""
from typing import Optional
import reflex as rx
from frontend.components.neu_components import (
    neu_button,
    neu_card,
    neu_input,
    status_pill,
)
from frontend.components.sidebar import sidebar
from frontend.state import AppState
from frontend.theme import (
    ACCENT_COLOR,
    BG_COLOR,
    FONT_SANS,
    FONT_SERIF,
    RADIUS_FULL,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_XL,
    SHADOW_INSET,
    SHADOW_RAISED,
    SHADOW_RAISED_SM,
    SURFACE_COLOR,
    TEXT_COLOR,
    TEXT_MUTED,
)


def auth_modal() -> rx.Component:
    """Minimal centered raised card authentication dialog."""
    return rx.dialog.root(
        rx.dialog.content(
            neu_card(
                rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.dialog.title(
                                rx.cond(
                                    AppState.auth_mode == "login",
                                    "Sign In to AutoAnalyst",
                                    "Create Analyst Account",
                                ),
                                font_size="1.25rem",
                                font_weight="700",
                                color=TEXT_COLOR,
                            ),
                            rx.dialog.description(
                                rx.cond(
                                    AppState.auth_mode == "login",
                                    "Access your isolated datasets and analytical reports.",
                                    "Register for multi-user isolated datasets and agent runs.",
                                ),
                                font_size="0.825rem",
                                color=TEXT_MUTED,
                            ),
                            spacing="0",
                            align_items="flex-start",
                        ),
                        rx.spacer(),
                        rx.dialog.close(
                            rx.icon(tag="x", size=18, color=TEXT_MUTED, cursor="pointer"),
                            on_click=AppState.toggle_auth_dialog,
                        ),
                        width="100%",
                        align_items="center",
                    ),
                    rx.cond(
                        AppState.auth_error != "",
                        rx.callout(
                            AppState.auth_error,
                            icon="triangle-alert",
                            color_scheme="red",
                            size="1",
                            width="100%",
                        ),
                    ),
                    rx.cond(
                        AppState.auth_mode == "register",
                        rx.vstack(
                            rx.text("Full Name", font_size="0.8rem", color=TEXT_MUTED, font_weight="500"),
                            neu_input(
                                placeholder="Lead Analyst",
                                value=AppState.auth_name_input,
                                on_change=AppState.set_auth_name,
                            ),
                            spacing="1",
                            width="100%",
                        ),
                    ),
                    rx.vstack(
                        rx.text("Email Address", font_size="0.8rem", color=TEXT_MUTED, font_weight="500"),
                        neu_input(
                            placeholder="analyst@example.com",
                            value=AppState.auth_email_input,
                            on_change=AppState.set_auth_email,
                            type="email",
                        ),
                        spacing="1",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Password", font_size="0.8rem", color=TEXT_MUTED, font_weight="500"),
                        neu_input(
                            placeholder="••••••••",
                            value=AppState.auth_password_input,
                            on_change=AppState.set_auth_password,
                            type="password",
                        ),
                        spacing="1",
                        width="100%",
                    ),
                    rx.cond(
                        AppState.auth_mode == "login",
                        neu_button(
                            "Sign In",
                            variant="primary",
                            width="100%",
                            padding="0.75rem",
                            on_click=AppState.login,
                        ),
                        neu_button(
                            "Create Account",
                            variant="primary",
                            width="100%",
                            padding="0.75rem",
                            on_click=AppState.register,
                        ),
                    ),
                    rx.hstack(
                        rx.cond(
                            AppState.auth_mode == "login",
                            rx.hstack(
                                rx.text("Don't have an account?", font_size="0.8rem", color=TEXT_MUTED),
                                rx.button(
                                    "Register",
                                    variant="ghost",
                                    size="1",
                                    color_scheme="orange",
                                    on_click=lambda: AppState.set_auth_mode("register"),
                                ),
                                spacing="1",
                                align_items="center",
                            ),
                            rx.hstack(
                                rx.text("Already have an account?", font_size="0.8rem", color=TEXT_MUTED),
                                rx.button(
                                    "Sign In",
                                    variant="ghost",
                                    size="1",
                                    color_scheme="orange",
                                    on_click=lambda: AppState.set_auth_mode("login"),
                                ),
                                spacing="1",
                                align_items="center",
                            ),
                        ),
                        justify="center",
                        width="100%",
                    ),
                    spacing="4",
                    width="100%",
                ),
                padding="2rem",
            ),
            background="transparent",
            box_shadow="none",
            border="none",
            max_width="440px",
        ),
        open=AppState.show_auth_dialog,
    )


def top_status_bar() -> rx.Component:
    """Free-form status bar with top-center pill (LLM provider + API status)."""
    return rx.hstack(
        rx.spacer(),
        # Center status pill
        status_pill(
            text=f"{AppState.active_provider.upper()} • {AppState.api_health_status}",
            icon="sparkles",
            status=rx.cond(AppState.api_health_status == "Healthy", "success", "warn"),
        ),
        rx.spacer(),
        # Top-right quick actions: Theme toggle + Auth badge
        rx.hstack(
            rx.box(
                rx.icon(
                    tag=rx.cond(AppState.theme_mode == "dark", "moon", "sun"),
                    size=14,
                    color=TEXT_MUTED,
                ),
                padding="0.45rem",
                border_radius=RADIUS_FULL,
                background_color=SURFACE_COLOR,
                box_shadow=SHADOW_RAISED_SM,
                cursor="pointer",
                on_click=AppState.toggle_theme,
                _hover={"box_shadow": SHADOW_INSET},
                transition="box-shadow 150ms ease",
            ),
            rx.cond(
                AppState.is_authenticated,
                rx.box(
                    rx.hstack(
                        rx.box(
                            width="6px",
                            height="6px",
                            border_radius=RADIUS_FULL,
                            background_color="var(--status-success)",
                        ),
                        rx.text(
                            AppState.current_user_name,
                            font_size="0.75rem",
                            font_weight="500",
                            color=TEXT_COLOR,
                        ),
                        spacing="2",
                        align_items="center",
                    ),
                    padding="0.35rem 0.75rem",
                    border_radius=RADIUS_FULL,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_RAISED_SM,
                ),
                neu_button(
                    "Sign In",
                    variant="secondary",
                    padding="0.35rem 0.75rem",
                    font_size="0.75rem",
                    on_click=AppState.toggle_auth_dialog,
                ),
            ),
            spacing="2",
            align_items="center",
        ),
        width="100%",
        padding_y="1rem",
        padding_x="1.5rem",
        align_items="center",
    )


def app_layout(page_title: str, content: rx.Component, max_width: str = "820px") -> rx.Component:
    """Standard app shell: Fixed left sidebar + calm centered content column (max ~820px)."""
    return rx.box(
        rx.hstack(
            sidebar(),
            rx.vstack(
                top_status_bar(),
                # Centered content column (max ~820px)
                rx.box(
                    content,
                    width="100%",
                    max_width=max_width,
                    margin="0 auto",
                    padding_x="1.5rem",
                    padding_bottom="3rem",
                    class_name="neu-page-container",
                ),
                auth_modal(),
                width="100%",
                min_height="100vh",
                overflow_y="auto",
                spacing="0",
                align_items="center",
            ),
            spacing="0",
            width="100%",
            min_height="100vh",
            align_items="flex-start",
        ),
        background_color=BG_COLOR,
        color=TEXT_COLOR,
        font_family=FONT_SANS,
        min_height="100vh",
        width="100vw",
        class_name=rx.cond(AppState.theme_mode == "light", "theme-light", ""),
    )
