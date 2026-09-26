from typing import Any
import reflex as rx

def stat_card(title: str, value: Any, subtitle: str, icon_name: str, color_accent: str = "#6366f1") -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(title, font_size="0.75rem", font_weight="600", color="#94a3b8", text_transform="uppercase", letter_spacing="0.05em"),
                rx.text(value, font_size="1.6rem", font_weight="700", color="#ffffff", line_height="1.1"),
                rx.text(subtitle, font_size="0.75rem", color="#64748b"),
                spacing="1",
                align_items="flex-start"
            ),
            rx.spacer(),
            rx.box(
                rx.icon(tag=icon_name, size=22, color=color_accent),
                padding="0.65rem",
                border_radius="0.5rem",
                background_color=f"{color_accent}15",
                border=f"1px solid {color_accent}30"
            ),
            width="100%",
            align_items="center"
        ),
        padding="1.25rem",
        border_radius="0.75rem",
        background_color="rgba(15, 23, 42, 0.65)",
        border="1px solid rgba(255, 255, 255, 0.08)",
        backdrop_filter="blur(8px)",
        box_shadow="0 4px 20px -2px rgba(0, 0, 0, 0.25)",
        width="100%",
        _hover={"border_color": "rgba(99, 102, 241, 0.3)", "transform": "translateY(-2px)"},
        transition="all 0.2s ease"
    )
