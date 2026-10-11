"""Theme tokens and reusable neumorphic style dictionaries for Reflex."""
from typing import Dict, Any

# Primary Palette & Tokens
BG_COLOR = "var(--bg)"
SURFACE_COLOR = "var(--surface)"
TEXT_COLOR = "var(--text)"
TEXT_MUTED = "var(--text-muted)"
ACCENT_COLOR = "var(--accent)"
ACCENT_HOVER = "var(--accent-hover)"
ACCENT_SUBTLE = "var(--accent-subtle)"

SHADOW_DARK = "var(--shadow-dark)"
SHADOW_LIGHT = "var(--shadow-light)"

SHADOW_RAISED = "var(--shadow-raised)"
SHADOW_RAISED_SM = "var(--shadow-raised-sm)"
SHADOW_INSET = "var(--shadow-inset)"
SHADOW_INSET_DEEP = "var(--shadow-inset-deep)"

RADIUS_SM = "10px"
RADIUS_MD = "14px"
RADIUS_LG = "18px"
RADIUS_XL = "24px"
RADIUS_FULL = "9999px"

FONT_SANS = "var(--font-sans)"
FONT_SERIF = "var(--font-serif)"

# Component Styles
CARD_STYLE: Dict[str, Any] = {
    "background_color": SURFACE_COLOR,
    "box_shadow": SHADOW_RAISED,
    "border_radius": RADIUS_LG,
    "padding": "1.5rem",
    "border": "none",
    "transition": "box-shadow 150ms ease, transform 150ms ease",
}

CARD_SM_STYLE: Dict[str, Any] = {
    "background_color": SURFACE_COLOR,
    "box_shadow": SHADOW_RAISED_SM,
    "border_radius": RADIUS_MD,
    "padding": "1rem",
    "border": "none",
    "transition": "box-shadow 150ms ease, transform 150ms ease",
}

INSET_CONTAINER_STYLE: Dict[str, Any] = {
    "background_color": SURFACE_COLOR,
    "box_shadow": SHADOW_INSET,
    "border_radius": RADIUS_LG,
    "padding": "1.25rem",
    "border": "none",
}

PRIMARY_BTN_STYLE: Dict[str, Any] = {
    "background_color": ACCENT_COLOR,
    "color": "#ffffff",
    "border_radius": RADIUS_MD,
    "border": "none",
    "font_weight": "500",
    "cursor": "pointer",
    "padding": "0.6rem 1.25rem",
    "box_shadow": "none",
    "transition": "background-color 150ms ease, transform 150ms ease",
    "_hover": {
        "background_color": ACCENT_HOVER,
    },
    "_active": {
        "transform": "translateY(1px)",
    },
}

SECONDARY_BTN_STYLE: Dict[str, Any] = {
    "background_color": SURFACE_COLOR,
    "color": TEXT_COLOR,
    "box_shadow": SHADOW_RAISED,
    "border_radius": RADIUS_MD,
    "border": "none",
    "font_weight": "500",
    "cursor": "pointer",
    "padding": "0.6rem 1.25rem",
    "transition": "box-shadow 150ms ease, transform 150ms ease",
    "_hover": {
        "box_shadow": SHADOW_RAISED_SM,
    },
    "_active": {
        "box_shadow": SHADOW_INSET,
    },
}

INPUT_STYLE: Dict[str, Any] = {
    "background_color": SURFACE_COLOR,
    "box_shadow": SHADOW_INSET,
    "color": TEXT_COLOR,
    "border_radius": RADIUS_MD,
    "border": "1px solid transparent",
    "padding": "0.65rem 1rem",
    "outline": "none",
    "transition": "box-shadow 150ms ease, border-color 150ms ease",
    "_focus": {
        "box_shadow": SHADOW_INSET_DEEP,
        "outline": f"2px solid {ACCENT_COLOR}",
        "outline_offset": "1px",
    },
}

STATUS_PILL_STYLE: Dict[str, Any] = {
    "background_color": SURFACE_COLOR,
    "box_shadow": SHADOW_RAISED_SM,
    "border_radius": RADIUS_FULL,
    "padding": "0.35rem 0.85rem",
    "border": "none",
    "display": "inline-flex",
    "align_items": "center",
    "gap": "0.5rem",
}
