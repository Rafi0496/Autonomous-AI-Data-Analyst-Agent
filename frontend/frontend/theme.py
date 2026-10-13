"""Theme tokens and reusable neumorphic style dictionaries for Reflex."""
from typing import Dict, Any

# Primary Palette & Tokens
BG_COLOR = "var(--bg)"
SURFACE_COLOR = "var(--surface)"
TEXT_COLOR = "var(--text-primary)"
TEXT_MUTED = "var(--text-secondary)"
TEXT_PRIMARY = "var(--text-primary)"
TEXT_SECONDARY = "var(--text-secondary)"
TEXT_TERTIARY = "var(--text-tertiary)"
TEXT_ON_PRIMARY = "var(--text-on-primary)"
TEXT_ERROR = "var(--text-error)"
TEXT_SUCCESS = "var(--text-success)"
TEXT_WARNING = "var(--text-warning)"
ACCENT_COLOR = "var(--accent)"
ACCENT_HOVER = "var(--accent-hover)"
ACCENT_SUBTLE = "var(--accent-subtle)"
ACCENT_TEXT = "var(--accent-text)"
BORDER_SUBTLE = "var(--border-subtle)"

# Supporting Pastel Palette
SAGE_COLOR = "var(--color-sage)"
SAGE_SUBTLE = "var(--color-sage-subtle)"
SAGE_TEXT = "var(--color-sage-text)"

DUSTY_BLUE_COLOR = "var(--color-dusty-blue)"
DUSTY_BLUE_SUBTLE = "var(--color-dusty-blue-subtle)"
DUSTY_BLUE_TEXT = "var(--color-dusty-blue-text)"

LAVENDER_COLOR = "var(--color-lavender)"
LAVENDER_SUBTLE = "var(--color-lavender-subtle)"
LAVENDER_TEXT = "var(--color-lavender-text)"

SAND_COLOR = "var(--color-sand)"
SAND_SUBTLE = "var(--color-sand-subtle)"
SAND_TEXT = "var(--color-sand-text)"

ROSE_MIST_COLOR = "var(--color-rose-mist)"
ROSE_MIST_SUBTLE = "var(--color-rose-mist-subtle)"
ROSE_MIST_TEXT = "var(--color-rose-mist-text)"

# Neumorphic Shadows
SHADOW_DARK = "var(--shadow-dark)"
SHADOW_LIGHT = "var(--shadow-light)"
SHADOW_RAISED = "var(--shadow-raised)"
SHADOW_RAISED_SM = "var(--shadow-raised-sm)"
SHADOW_INSET = "var(--shadow-inset)"
SHADOW_INSET_DEEP = "var(--shadow-inset-deep)"

# Radii (Consistent 8px grid alignment: 12 / 16 / 20 / 24)
RADIUS_SM = "12px"
RADIUS_MD = "16px"
RADIUS_LG = "20px"
RADIUS_XL = "24px"
RADIUS_FULL = "9999px"

# Typography
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
    "border_radius": RADIUS_MD,
    "padding": "1.25rem",
    "border": "none",
}

PRIMARY_BTN_STYLE: Dict[str, Any] = {
    "background_color": ACCENT_COLOR,
    "color": ACCENT_TEXT,
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
    "_focus_visible": {
        "outline": f"2px solid {ACCENT_COLOR}",
        "outline_offset": "2px",
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
    "_focus_visible": {
        "outline": f"2px solid {ACCENT_COLOR}",
        "outline_offset": "2px",
    },
}

INPUT_STYLE: Dict[str, Any] = {
    "background_color": SURFACE_COLOR,
    "box_shadow": SHADOW_INSET,
    "color": TEXT_COLOR,
    "border_radius": RADIUS_MD,
    "border": "2px solid transparent",
    "padding": "0.65rem 1rem",
    "outline": "none",
    "transition": "box-shadow 150ms ease, border-color 150ms ease",
    "_focus_within": {
        "box_shadow": SHADOW_INSET_DEEP,
        "border_color": ACCENT_COLOR,
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
