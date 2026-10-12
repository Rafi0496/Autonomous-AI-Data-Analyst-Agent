from typing import Any
import reflex as rx
from frontend.components.neu_components import neu_card
from frontend.theme import (
    ACCENT_COLOR,
    RADIUS_FULL,
    SHADOW_INSET,
    SURFACE_COLOR,
    TEXT_COLOR,
    TEXT_MUTED,
)

def stat_card(title: str, value: Any, subtitle: str, icon_name: str, color_accent: str = ACCENT_COLOR) -> rx.Component:
    """Neumorphic stat card with clean typography and tabular numerals."""
    return neu_card(
        rx.hstack(
            rx.vstack(
                rx.text(title, font_size="0.75rem", font_weight="600", color=TEXT_MUTED, text_transform="uppercase", letter_spacing="0.05em"),
                rx.text(value, font_size="1.55rem", font_weight="700", color=TEXT_COLOR, line_height="1.1", class_name="tabular-nums"),
                rx.text(subtitle, font_size="0.72rem", color=TEXT_MUTED),
                spacing="1",
                align_items="flex-start",
            ),
            rx.spacer(),
            rx.box(
                rx.icon(tag=icon_name, size=20, color=color_accent),
                padding="0.6rem",
                border_radius=RADIUS_FULL,
                background_color=SURFACE_COLOR,
                box_shadow=SHADOW_INSET,
            ),
            width="100%",
            align_items="center",
        ),
        sm=True,
        width="100%",
    )

