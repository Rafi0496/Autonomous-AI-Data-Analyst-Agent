"""Reusable Neumorphic + Minimalist Component Library for Autonomous AI Data Analyst Agent."""
from typing import Any, Callable, Dict, List, Optional, Union
import reflex as rx
from frontend.theme import (
    ACCENT_COLOR,
    ACCENT_HOVER,
    ACCENT_SUBTLE,
    ACCENT_TEXT,
    CARD_SM_STYLE,
    CARD_STYLE,
    FONT_SANS,
    FONT_SERIF,
    INPUT_STYLE,
    INSET_CONTAINER_STYLE,
    PRIMARY_BTN_STYLE,
    RADIUS_FULL,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    RADIUS_XL,
    SECONDARY_BTN_STYLE,
    SHADOW_INSET,
    SHADOW_INSET_DEEP,
    SHADOW_RAISED,
    SHADOW_RAISED_SM,
    STATUS_PILL_STYLE,
    SURFACE_COLOR,
    TEXT_COLOR,
    TEXT_MUTED,
)


def neu_card(*children: rx.Component, sm: bool = False, **props) -> rx.Component:
    """Neumorphic raised card container with soft 16-20px radii and dual tonal shadows."""
    base_style = CARD_SM_STYLE if sm else CARD_STYLE
    merged = {**base_style, **props}
    return rx.box(*children, **merged)


def neu_inset_card(*children: rx.Component, **props) -> rx.Component:
    """Neumorphic inset container (pressed/sunken surface)."""
    merged = {**INSET_CONTAINER_STYLE, **props}
    return rx.box(*children, **merged)


def neu_button(
    *children: rx.Component,
    variant: str = "primary",  # "primary" | "secondary" | "ghost"
    is_loading: Optional[Union[bool, rx.Var[bool]]] = None,
    **props,
) -> rx.Component:
    """Neumorphic button.
    Primary: Flat muted slate-teal (#4F7C82) fill with white text.
    Secondary: Raised soft surface with dual tonal shadows.
    """
    if variant == "primary":
        base_style = PRIMARY_BTN_STYLE
    elif variant == "secondary":
        base_style = SECONDARY_BTN_STYLE
    else:
        base_style = {
            "background_color": "transparent",
            "color": TEXT_MUTED,
            "border": "none",
            "cursor": "pointer",
            "padding": "0.5rem 0.85rem",
            "border_radius": RADIUS_MD,
            "transition": "all 150ms ease",
            "_hover": {"color": TEXT_COLOR, "background_color": SURFACE_COLOR},
        }

    merged = {**base_style, **props}
    if is_loading is not None:
        merged["is_loading"] = is_loading

    return rx.button(*children, **merged)


def neu_icon_button(
    icon: str,
    on_click: Optional[Any] = None,
    size: int = 18,
    variant: str = "secondary",
    tooltip: Optional[str] = None,
    **props,
) -> rx.Component:
    """Circular or rounded soft icon button."""
    btn = neu_button(
        rx.icon(tag=icon, size=size),
        variant=variant,
        on_click=on_click,
        padding="0.6rem",
        border_radius=RADIUS_FULL,
        display="inline-flex",
        align_items="center",
        justify_content="center",
        **props,
    )
    if tooltip is not None:
        return rx.tooltip(btn, content=tooltip)
    return btn


def neu_input(
    placeholder: str = "",
    value: Optional[Union[str, rx.Var[str]]] = None,
    on_change: Optional[Any] = None,
    type: str = "text",
    width: str = "100%",
    debounce_timeout: int = 200,
    **props,
) -> rx.Component:
    """Sunken/inset text input with ONE container only and stripped inner input."""
    input_props = {
        "type": type,
        "placeholder": placeholder,
        "class_name": "neu-input-field",
        "width": "100%",
        "debounce_timeout": debounce_timeout,
    }
    if value is not None:
        input_props["value"] = value
    if on_change is not None:
        input_props["on_change"] = on_change

    return rx.box(
        rx.input(**input_props),
        class_name="neu-input-container",
        padding="0.65rem 1rem",
        width=width,
        **props,
    )


def neu_toggle(
    checked: Union[bool, rx.Var[bool]],
    on_change: Any,
    label: str = "",
    **props,
) -> rx.Component:
    """Neumorphic toggle with teal active indicator."""
    return rx.hstack(
        rx.switch(
            checked=checked,
            on_change=on_change,
            color_scheme="teal",
            size="2",
            **props,
        ),
        rx.cond(
            label != "",
            rx.text(label, font_size="0.85rem", color=TEXT_COLOR, font_weight="500"),
        ),
        spacing="2",
        align_items="center",
    )


def neu_tabs(
    tabs: List[Dict[str, str]],  # [{"id": "tab1", "label": "Tab 1", "icon": "upload"}]
    active_tab: Union[str, rx.Var[str]],
    on_select: Callable[[str], Any],
    **props,
) -> rx.Component:
    """Neumorphic tab switcher with inset track and raised/active pill."""
    return rx.box(
        rx.hstack(
            *[
                rx.box(
                    rx.hstack(
                        rx.cond(
                            tab.get("icon", "") != "",
                            rx.icon(
                                tag=tab.get("icon", "circle"),
                                size=14,
                                color=rx.cond(
                                    active_tab == tab["id"],
                                    ACCENT_COLOR,
                                    TEXT_MUTED,
                                ),
                            ),
                        ),
                        rx.text(
                            tab["label"],
                            font_size="0.825rem",
                            font_weight=rx.cond(active_tab == tab["id"], "600", "400"),
                            color=rx.cond(active_tab == tab["id"], TEXT_COLOR, TEXT_MUTED),
                        ),
                        spacing="2",
                        align_items="center",
                    ),
                    padding_y="0.45rem",
                    padding_x="0.9rem",
                    border_radius=RADIUS_MD,
                    cursor="pointer",
                    background_color=rx.cond(
                        active_tab == tab["id"],
                        SURFACE_COLOR,
                        "transparent",
                    ),
                    box_shadow=rx.cond(
                        active_tab == tab["id"],
                        SHADOW_RAISED_SM,
                        "none",
                    ),
                    transition="all 150ms ease",
                    on_click=on_select(tab["id"]),
                )
                for tab in tabs
            ],
            spacing="1",
            align_items="center",
        ),
        background_color=SURFACE_COLOR,
        box_shadow=SHADOW_INSET,
        border_radius=RADIUS_LG,
        padding="0.3rem",
        display="inline-block",
        **props,
    )


def progress_track(
    percent: Union[int, float, rx.Var[int], rx.Var[float]],
    label: str = "",
    height: str = "8px",
    **props,
) -> rx.Component:
    """Smooth progress bar with inset track, flat accent fill, and no shimmer."""
    return rx.vstack(
        rx.cond(
            label != "",
            rx.hstack(
                rx.text(label, font_size="0.8rem", color=TEXT_MUTED),
                rx.spacer(),
                rx.text(f"{percent}%", font_size="0.8rem", color=TEXT_COLOR, font_weight="600", class_name="tabular-nums"),
                width="100%",
                align_items="center",
            ),
        ),
        rx.box(
            rx.box(
                background_color=ACCENT_COLOR,
                height="100%",
                border_radius=RADIUS_FULL,
                width=f"{percent}%",
                transition="width 300ms ease-out",
            ),
            background_color=SURFACE_COLOR,
            box_shadow=SHADOW_INSET,
            border_radius=RADIUS_FULL,
            height=height,
            width="100%",
            overflow="hidden",
        ),
        spacing="1",
        width="100%",
        **props,
    )


def status_pill(
    text: Union[str, rx.Var[str]],
    icon: str = "circle-check",
    status: str = "info",  # "success" | "warn" | "error" | "info"
    **props,
) -> rx.Component:
    """High-contrast semantic status pill with icon + text (never color alone, WCAG compliant)."""
    if isinstance(status, rx.Var):
        pill_color = rx.cond(
            status == "success",
            "var(--status-success)",
            rx.cond(
                status == "warn",
                "var(--status-warning)",
                rx.cond(status == "error", "var(--status-error)", "var(--status-info)"),
            ),
        )
        pill_bg = rx.cond(
            status == "success",
            "var(--status-success-bg)",
            rx.cond(
                status == "warn",
                "var(--status-warning-bg)",
                rx.cond(status == "error", "var(--status-error-bg)", "var(--status-info-bg)"),
            ),
        )
    else:
        color_map = {
            "success": "var(--status-success)",
            "warn": "var(--status-warning)",
            "error": "var(--status-error)",
            "info": "var(--status-info)",
        }
        bg_map = {
            "success": "var(--status-success-bg)",
            "warn": "var(--status-warning-bg)",
            "error": "var(--status-error-bg)",
            "info": "var(--status-info-bg)",
        }
        pill_color = color_map.get(status, "var(--status-info)")
        pill_bg = bg_map.get(status, "var(--status-info-bg)")

    return rx.box(
        rx.hstack(
            rx.icon(tag=icon, size=13, color=pill_color),
            rx.text(
                text,
                font_size="0.75rem",
                font_weight="600",
                color=pill_color,
                letter_spacing="0.01em",
            ),
            spacing="2",
            align_items="center",
        ),
        background_color=pill_bg,
        border_radius=RADIUS_FULL,
        padding="0.3rem 0.75rem",
        box_shadow=SHADOW_RAISED_SM,
        display="inline-flex",
        align_items="center",
        **props,
    )


def empty_state(
    title: str,
    description: str,
    icon: str = "inbox",
    action_button: Optional[rx.Component] = None,
    **props,
) -> rx.Component:
    """Honest empty state card without fabricated sample numbers or metrics."""
    items = [
        rx.box(
            rx.icon(tag=icon, size=28, color=TEXT_MUTED),
            padding="1rem",
            border_radius=RADIUS_FULL,
            background_color=SURFACE_COLOR,
            box_shadow=SHADOW_INSET,
        ),
        rx.text(title, font_weight="600", font_size="1rem", color=TEXT_COLOR),
        rx.text(
            description,
            font_size="0.85rem",
            color=TEXT_MUTED,
            text_align="center",
            max_width="420px",
            line_height="1.5",
        ),
    ]
    if action_button is not None:
        items.append(action_button)

    return neu_card(
        rx.vstack(
            *items,
            spacing="3",
            align_items="center",
            justify_content="center",
            padding_y="2.5rem",
            width="100%",
        ),
        width="100%",
        **props,
    )


def citation_chip(
    metric_key: str,
    value: Union[str, float, int],
    source: Optional[str] = None,
    on_click: Optional[Any] = None,
) -> rx.Component:
    """Minimalist citation chip grounding an analytical finding in computed facts."""
    return rx.box(
        rx.hstack(
            rx.icon(tag="bookmark", size=11, color=ACCENT_COLOR),
            rx.text(f"{metric_key}: {value}", font_size="0.72rem", font_weight="500", color=TEXT_COLOR),
            rx.cond(
                source is not None,
                rx.text(f"({source})", font_size="0.68rem", color=TEXT_MUTED),
            ),
            spacing="1",
            align_items="center",
        ),
        background_color=SURFACE_COLOR,
        box_shadow=SHADOW_RAISED_SM,
        border_radius=RADIUS_SM,
        padding="0.25rem 0.55rem",
        cursor="pointer" if on_click else "default",
        on_click=on_click,
        _hover={"box_shadow": SHADOW_INSET} if on_click else {},
        transition="box-shadow 150ms ease",
        display="inline-block",
    )


def hero_input(
    input_value: Union[str, rx.Var[str]],
    on_change: Any,
    on_submit: Any,
    dataset_options: Any,
    selected_dataset: Union[str, rx.Var[str]],
    on_select_dataset: Any,
    on_attach_file: Optional[Any] = None,
    on_key_down: Optional[Any] = None,
    is_loading: Union[bool, rx.Var[bool]] = False,
    placeholder: str = "Ask a question or describe what you want to analyze... (Enter sends, Shift+Enter for newline)",
    **props,
) -> rx.Component:
    """Clean hero input container with textarea supporting Enter to send, Shift+Enter newline, and clean dataset selector."""
    return rx.box(
        rx.vstack(
            # Top row: '+' button, prompt textarea, and submit action
            rx.hstack(
                rx.box(
                    rx.icon(tag="plus", size=16, color=ACCENT_COLOR),
                    padding="0.55rem",
                    border_radius=RADIUS_FULL,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_RAISED_SM,
                    cursor="pointer",
                    on_click=on_attach_file,
                    _hover={"box_shadow": SHADOW_INSET},
                    transition="box-shadow 150ms ease",
                    title="Upload dataset",
                    flex_shrink=0,
                ),
                rx.text_area(
                    id="hero-input-textarea",
                    placeholder=placeholder,
                    value=input_value,
                    on_change=on_change,
                    on_key_down=on_key_down,
                    debounce_timeout=200,
                    class_name="neu-input-field",
                    width="100%",
                    rows="1",
                    resize="none",
                    border="none",
                    outline="none",
                    background="transparent",
                    color=TEXT_COLOR,
                    _focus={"outline": "none"},
                ),
                rx.spacer(),
                neu_button(
                    rx.icon(tag="arrow-up", size=16),
                    variant="primary",
                    is_loading=is_loading,
                    is_disabled=is_loading,
                    on_click=on_submit,
                    border_radius=RADIUS_FULL,
                    padding="0.55rem",
                    width="36px",
                    height="36px",
                    display="inline-flex",
                    align_items="center",
                    justify_content="center",
                ),
                spacing="3",
                align_items="center",
                width="100%",
            ),
            # Bottom row: Clean Dataset selector on left
            rx.hstack(
                rx.hstack(
                    rx.icon(tag="database", size=13, color=TEXT_MUTED),
                    rx.select(
                        items=dataset_options,
                        value=selected_dataset,
                        on_change=on_select_dataset,
                        placeholder="Select dataset...",
                        size="1",
                        variant="ghost",
                        color_scheme="gray",
                    ),
                    spacing="1",
                    align_items="center",
                ),
                spacing="2",
                align_items="center",
                width="100%",
                padding_top="0.25rem",
            ),
            spacing="3",
            width="100%",
        ),
        class_name="neu-input-container",
        border_radius=RADIUS_XL,
        padding="1rem 1.25rem",
        width="100%",
        **props,
    )
