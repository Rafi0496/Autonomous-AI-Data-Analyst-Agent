"""Dedicated Login & Register Page with Minimal Centered Raised Neumorphic Card."""
import reflex as rx
from frontend.components.neu_components import (
    neu_button,
    neu_card,
    neu_input,
)
from frontend.state import AppState
from frontend.theme import (
    ACCENT_COLOR,
    BG_COLOR,
    FONT_SANS,
    FONT_SERIF,
    RADIUS_FULL,
    RADIUS_LG,
    RADIUS_MD,
    SHADOW_INSET,
    SHADOW_RAISED,
    SHADOW_RAISED_SM,
    SURFACE_COLOR,
    TEXT_COLOR,
    TEXT_MUTED,
)


def login_page() -> rx.Component:
    """Minimal centered raised card for Login and Registration."""
    return rx.box(
        rx.vstack(
            neu_card(
                rx.vstack(
                    # Header with Brand Mark
                    rx.vstack(
                        rx.box(
                            rx.icon(tag="bot", size=26, color="#ffffff"),
                            padding="0.75rem",
                            border_radius=RADIUS_FULL,
                            background_color=ACCENT_COLOR,
                            box_shadow=SHADOW_RAISED_SM,
                            display="inline-flex",
                            align_items="center",
                            justify_content="center",
                        ),
                        rx.text(
                            rx.cond(
                                AppState.auth_mode == "login",
                                "Sign In to AutoAnalyst",
                                "Create Analyst Account",
                            ),
                            font_family=FONT_SERIF,
                            font_size="1.6rem",
                            font_weight="400",
                            color=TEXT_COLOR,
                            letter_spacing="-0.01em",
                            text_align="center",
                        ),
                        rx.text(
                            rx.cond(
                                AppState.auth_mode == "login",
                                "Access your isolated datasets, agent runs, and reports.",
                                "Register for tenant-isolated data intelligence and autonomous analysis.",
                            ),
                            font_size="0.825rem",
                            color=TEXT_MUTED,
                            text_align="center",
                            max_width="320px",
                            line_height="1.4",
                        ),
                        spacing="2",
                        align_items="center",
                        width="100%",
                        padding_bottom="0.5rem",
                    ),

                    # Mode Tabs (Sign In / Register)
                    rx.box(
                        rx.hstack(
                            rx.box(
                                rx.text(
                                    "Sign In",
                                    font_size="0.825rem",
                                    font_weight=rx.cond(AppState.auth_mode == "login", "600", "400"),
                                    color=rx.cond(AppState.auth_mode == "login", TEXT_COLOR, TEXT_MUTED),
                                ),
                                padding_y="0.45rem",
                                padding_x="1.25rem",
                                border_radius=RADIUS_MD,
                                cursor="pointer",
                                background_color=rx.cond(AppState.auth_mode == "login", SURFACE_COLOR, "transparent"),
                                box_shadow=rx.cond(AppState.auth_mode == "login", SHADOW_RAISED_SM, "none"),
                                on_click=lambda: AppState.set_auth_mode("login"),
                                transition="all 150ms ease",
                            ),
                            rx.box(
                                rx.text(
                                    "Create Account",
                                    font_size="0.825rem",
                                    font_weight=rx.cond(AppState.auth_mode == "register", "600", "400"),
                                    color=rx.cond(AppState.auth_mode == "register", TEXT_COLOR, TEXT_MUTED),
                                ),
                                padding_y="0.45rem",
                                padding_x="1.25rem",
                                border_radius=RADIUS_MD,
                                cursor="pointer",
                                background_color=rx.cond(AppState.auth_mode == "register", SURFACE_COLOR, "transparent"),
                                box_shadow=rx.cond(AppState.auth_mode == "register", SHADOW_RAISED_SM, "none"),
                                on_click=lambda: AppState.set_auth_mode("register"),
                                transition="all 150ms ease",
                            ),
                            spacing="1",
                            align_items="center",
                        ),
                        background_color=SURFACE_COLOR,
                        box_shadow=SHADOW_INSET,
                        border_radius=RADIUS_LG,
                        padding="0.25rem",
                        width="100%",
                        display="flex",
                        justify_content="center",
                    ),

                    # Error Callout (if any)
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

                    # Form Fields
                    rx.cond(
                        AppState.auth_mode == "register",
                        rx.vstack(
                            rx.text("Full Name", font_size="0.8rem", color=TEXT_MUTED, font_weight="500"),
                            neu_input(
                                placeholder="Alex Morgan",
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

                    # Submit Button
                    rx.cond(
                        AppState.auth_mode == "login",
                        neu_button(
                            "Sign In",
                            variant="primary",
                            width="100%",
                            padding="0.75rem",
                            is_loading=AppState.is_loading,
                            on_click=AppState.login,
                        ),
                        neu_button(
                            "Create Account",
                            variant="primary",
                            width="100%",
                            padding="0.75rem",
                            is_loading=AppState.is_loading,
                            on_click=AppState.register,
                        ),
                    ),

                    # Bottom Switch link
                    rx.hstack(
                        rx.cond(
                            AppState.auth_mode == "login",
                            rx.hstack(
                                rx.text("Don't have an account?", font_size="0.8rem", color=TEXT_MUTED),
                                rx.button(
                                    "Register",
                                    variant="ghost",
                                    size="1",
                                    color_scheme="teal",
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
                                    color_scheme="teal",
                                    on_click=lambda: AppState.set_auth_mode("login"),
                                ),
                                spacing="1",
                                align_items="center",
                            ),
                        ),
                        justify="center",
                        width="100%",
                    ),

                    # Continue as Guest / Back link
                    rx.link(
                        rx.hstack(
                            rx.icon(tag="arrow-left", size=13, color=TEXT_MUTED),
                            rx.text("Continue as guest", font_size="0.78rem", color=TEXT_MUTED),
                            spacing="1",
                            align_items="center",
                        ),
                        href="/",
                        text_decoration="none",
                        _hover={"color": TEXT_COLOR},
                    ),

                    spacing="4",
                    width="100%",
                    align_items="center",
                ),
                width="100%",
                max_width="420px",
                padding="2.25rem",
            ),
            width="100%",
            min_height="100vh",
            display="flex",
            align_items="center",
            justify_content="center",
            padding="1.5rem",
            class_name="neu-page-container",
        ),
        background_color=BG_COLOR,
        color=TEXT_COLOR,
        font_family=FONT_SANS,
        min_height="100vh",
        width="100vw",
    )
