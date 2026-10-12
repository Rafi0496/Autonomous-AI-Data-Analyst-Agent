"""Neumorphic Collapsible Left Sidebar Component (280px expanded, 72px rail)."""
import reflex as rx
from frontend.components.neu_components import (
    neu_icon_button,
)
from frontend.state import AppState, RecentJobModel
from frontend.theme import (
    ACCENT_COLOR,
    FONT_SANS,
    RADIUS_FULL,
    RADIUS_MD,
    RADIUS_SM,
    SHADOW_INSET,
    SHADOW_RAISED_SM,
    SURFACE_COLOR,
    TEXT_COLOR,
    TEXT_MUTED,
)


def sidebar_nav_item(label: str, icon: str, route: str, tab_id: str) -> rx.Component:
    """Primary nav item with flat icon in rail, label in expanded mode, and clean tooltip."""
    is_active = AppState.active_tab == tab_id

    inner_content = rx.hstack(
        rx.icon(
            tag=icon,
            size=17,
            color=rx.cond(is_active, ACCENT_COLOR, TEXT_COLOR),
            flex_shrink=0,
        ),
        rx.text(
            label,
            class_name="sidebar-label",
            font_weight=rx.cond(is_active, "600", "400"),
            color=rx.cond(is_active, TEXT_COLOR, TEXT_MUTED),
            font_size="0.875rem",
        ),
        spacing="3",
        align_items="center",
        justify_content=rx.cond(AppState.sidebar_collapsed, "center", "flex-start"),
        padding_y="0.6rem",
        padding_x=rx.cond(AppState.sidebar_collapsed, "0.5rem", "0.85rem"),
        border_radius=RADIUS_MD,
        background_color=SURFACE_COLOR,
        box_shadow=rx.cond(is_active, SHADOW_INSET, "none"),
        _hover={
            "box_shadow": rx.cond(is_active, SHADOW_INSET, SHADOW_RAISED_SM),
            "color": TEXT_COLOR,
        },
        transition="all 150ms ease",
        width="100%",
    )

    link = rx.link(
        inner_content,
        href=route,
        text_decoration="none",
        width="100%",
        on_click=AppState.select_tab(tab_id),
    )

    # In collapsed rail mode, wrap in flat tonal tooltip
    return rx.cond(
        AppState.sidebar_collapsed,
        rx.tooltip(link, content=label),
        link,
    )


def recent_job_item(job: RecentJobModel) -> rx.Component:
    """Recent analysis job entry with title, status dot, and pin toggle."""
    status_color = rx.cond(
        job.status == "completed",
        "var(--status-success)",
        rx.cond(job.status == "failed", "var(--status-error)", "var(--status-warning)"),
    )

    return rx.link(
        rx.hstack(
            # Status dot
            rx.box(
                width="7px",
                height="7px",
                border_radius=RADIUS_FULL,
                background_color=status_color,
                flex_shrink=0,
            ),
            # Dataset name or goal
            rx.text(
                job.dataset_name,
                font_size="0.8rem",
                color=TEXT_COLOR,
                class_name="sidebar-label",
                max_width="160px",
            ),
            rx.spacer(),
            # Pin icon
            rx.box(
                rx.icon(
                    tag="pin",
                    size=12,
                    color=rx.cond(job.is_pinned, ACCENT_COLOR, TEXT_MUTED),
                ),
                cursor="pointer",
                padding="0.2rem",
                border_radius=RADIUS_SM,
                _hover={"color": ACCENT_COLOR},
                on_click=AppState.toggle_pin_job(job.job_id),
            ),
            spacing="2",
            align_items="center",
            padding_y="0.45rem",
            padding_x="0.65rem",
            border_radius=RADIUS_SM,
            background_color="transparent",
            _hover={
                "background_color": SURFACE_COLOR,
                "box_shadow": SHADOW_RAISED_SM,
            },
            transition="all 150ms ease",
            width="100%",
        ),
        href="/dashboard",
        text_decoration="none",
        width="100%",
        on_click=AppState.load_job(job.job_id),
    )


def sidebar_section_header(title: str) -> rx.Component:
    """Minimal section divider title."""
    return rx.text(
        title.upper(),
        font_size="0.68rem",
        font_weight="700",
        color=TEXT_MUTED,
        letter_spacing="0.08em",
        padding_x="0.65rem",
        margin_top="1rem",
        margin_bottom="0.35rem",
        class_name="sidebar-label",
    )


def sidebar() -> rx.Component:
    """Collapsible Left Sidebar (280px desktop, collapses to 72px rail, overlay drawer <900px)."""
    return rx.box(
        rx.vstack(
            # 1. Top Brand Mark & Toggle
            rx.hstack(
                rx.hstack(
                    rx.box(
                        rx.icon(tag="bot", size=18, color="#FFFFFF"),
                        padding="0.45rem",
                        border_radius=RADIUS_MD,
                        background_color=ACCENT_COLOR,
                        box_shadow=SHADOW_RAISED_SM,
                        flex_shrink=0,
                    ),
                    rx.vstack(
                        rx.text(
                            "AutoAnalyst",
                            font_size="1rem",
                            font_weight="700",
                            color=TEXT_COLOR,
                            line_height="1.2",
                            class_name="sidebar-label",
                        ),
                        rx.text(
                            "Autonomous Agent",
                            font_size="0.7rem",
                            color=TEXT_MUTED,
                            class_name="sidebar-label",
                        ),
                        spacing="0",
                        align_items="flex-start",
                        class_name="sidebar-label",
                    ),
                    spacing="2",
                    align_items="center",
                ),
                rx.spacer(),
                # Collapse / Expand toggle button with accessible aria attributes
                rx.box(
                    rx.button(
                        rx.icon(
                            tag=rx.cond(AppState.sidebar_collapsed, "panel-left-open", "panel-left-close"),
                            size=16,
                            color=TEXT_COLOR,
                        ),
                        on_click=AppState.toggle_sidebar,
                        background_color=SURFACE_COLOR,
                        box_shadow=SHADOW_RAISED_SM,
                        border_radius=RADIUS_FULL,
                        padding="0.45rem",
                        cursor="pointer",
                        border="none",
                        _hover={"box_shadow": SHADOW_INSET},
                        transition="box-shadow 150ms ease",
                        custom_attrs={
                            "aria-expanded": rx.cond(AppState.sidebar_collapsed, "false", "true"),
                            "aria-label": rx.cond(AppState.sidebar_collapsed, "Expand sidebar", "Collapse sidebar"),
                        },
                    ),
                ),
                width="100%",
                align_items="center",
                justify_content=rx.cond(AppState.sidebar_collapsed, "center", "space-between"),
                padding_bottom="0.85rem",
            ),

            # 2. Search container (inset, no inner box)
            rx.cond(
                AppState.sidebar_collapsed,
                # In collapsed mode: centered search icon button that expands sidebar
                rx.box(
                    rx.tooltip(
                        rx.box(
                            rx.icon(tag="search", size=16, color=TEXT_MUTED),
                            padding="0.55rem",
                            border_radius=RADIUS_MD,
                            background_color=SURFACE_COLOR,
                            box_shadow=SHADOW_INSET,
                            cursor="pointer",
                            on_click=AppState.toggle_sidebar,
                            display="flex",
                            align_items="center",
                            justify_content="center",
                        ),
                        content="Search analyses",
                    ),
                    width="100%",
                    display="flex",
                    justify_content="center",
                    margin_bottom="0.75rem",
                ),
                # In expanded mode: clean single inset container
                rx.box(
                    rx.hstack(
                        rx.icon(tag="search", size=14, color=TEXT_MUTED, flex_shrink=0),
                        rx.input(
                            placeholder="Search analyses...",
                            value=AppState.sidebar_search_query,
                            on_change=AppState.set_sidebar_search,
                            class_name="neu-input-field",
                            width="100%",
                        ),
                        spacing="2",
                        align_items="center",
                        width="100%",
                    ),
                    class_name="neu-input-container",
                    padding="0.45rem 0.75rem",
                    width="100%",
                    margin_bottom="0.75rem",
                ),
            ),

            # 3. Primary Navigation Items
            rx.vstack(
                sidebar_nav_item("New analysis", "circle-plus", "/", "home"),
                sidebar_nav_item("Datasets", "database", "/upload", "upload"),
                sidebar_nav_item("Run monitor", "activity", "/run", "run"),
                sidebar_nav_item("Dashboard", "layout-dashboard", "/dashboard", "dashboard"),
                sidebar_nav_item("Chat", "message-square", "/chat", "chat"),
                sidebar_nav_item("Reports", "file-text", "/reports", "reports"),
                sidebar_nav_item("Settings", "settings", "/settings", "settings"),
                spacing="1",
                width="100%",
            ),

            # 4. Pinned Analyses (Cleanly hidden in collapsed rail)
            rx.box(
                rx.cond(
                    AppState.pinned_jobs.length() > 0,
                    rx.vstack(
                        sidebar_section_header("Pinned"),
                        rx.foreach(AppState.pinned_jobs, lambda job: recent_job_item(job)),
                        spacing="1",
                        width="100%",
                    ),
                ),
                class_name="sidebar-collapsible-section",
                width="100%",
                custom_attrs={"aria-hidden": rx.cond(AppState.sidebar_collapsed, "true", "false")},
            ),

            # 5. Recent Analyses (Grouped Today / Yesterday / Older)
            rx.box(
                rx.vstack(
                    sidebar_section_header("Recent Analyses"),
                    # Today
                    rx.cond(
                        AppState.today_jobs.length() > 0,
                        rx.vstack(
                            rx.text("Today", font_size="0.72rem", color=TEXT_MUTED, font_weight="600", padding_x="0.65rem"),
                            rx.foreach(AppState.today_jobs, lambda j: recent_job_item(j)),
                            spacing="1",
                            width="100%",
                        ),
                    ),
                    # Yesterday
                    rx.cond(
                        AppState.yesterday_jobs.length() > 0,
                        rx.vstack(
                            rx.text("Yesterday", font_size="0.72rem", color=TEXT_MUTED, font_weight="600", padding_x="0.65rem"),
                            rx.foreach(AppState.yesterday_jobs, lambda j: recent_job_item(j)),
                            spacing="1",
                            width="100%",
                        ),
                    ),
                    # Older
                    rx.cond(
                        AppState.older_jobs.length() > 0,
                        rx.vstack(
                            rx.text("Older", font_size="0.72rem", color=TEXT_MUTED, font_weight="600", padding_x="0.65rem"),
                            rx.foreach(AppState.older_jobs, lambda j: recent_job_item(j)),
                            spacing="1",
                            width="100%",
                        ),
                    ),
                    # Empty state when no jobs yet
                    rx.cond(
                        AppState.recent_jobs.length() == 0,
                        rx.text(
                            "No past runs found",
                            font_size="0.75rem",
                            color=TEXT_MUTED,
                            padding_x="0.65rem",
                            font_style="italic",
                        ),
                    ),
                    spacing="2",
                    width="100%",
                    overflow_y="auto",
                    max_height="32vh",
                ),
                class_name="sidebar-collapsible-section",
                width="100%",
                custom_attrs={"aria-hidden": rx.cond(AppState.sidebar_collapsed, "true", "false")},
            ),

            rx.spacer(),

            # 6. Bottom User Chip
            rx.cond(
                AppState.sidebar_collapsed,
                # Collapsed Avatar with tooltip
                rx.box(
                    rx.tooltip(
                        rx.box(
                            rx.text(AppState.user_initial, font_weight="700", font_size="0.85rem", color="#FFFFFF"),
                            width="34px",
                            height="34px",
                            border_radius=RADIUS_FULL,
                            background_color=ACCENT_COLOR,
                            display="flex",
                            align_items="center",
                            justify_content="center",
                            cursor="pointer",
                            on_click=AppState.toggle_auth_dialog,
                        ),
                        content=rx.cond(AppState.is_authenticated, AppState.current_user_name, "Account sign-in"),
                    ),
                    display="flex",
                    justify_content="center",
                    width="100%",
                ),
                # Expanded User Card
                rx.box(
                    rx.hstack(
                        # Avatar circle
                        rx.box(
                            rx.text(AppState.user_initial, font_weight="700", font_size="0.85rem", color="#FFFFFF"),
                            width="34px",
                            height="34px",
                            border_radius=RADIUS_FULL,
                            background_color=ACCENT_COLOR,
                            box_shadow=SHADOW_RAISED_SM,
                            display="flex",
                            align_items="center",
                            justify_content="center",
                            flex_shrink=0,
                        ),
                        # Name & Email
                        rx.vstack(
                            rx.text(
                                rx.cond(AppState.is_authenticated, AppState.current_user_name, "Guest User"),
                                font_size="0.825rem",
                                font_weight="600",
                                color=TEXT_COLOR,
                                class_name="sidebar-label",
                                max_width="135px",
                            ),
                            rx.text(
                                rx.cond(AppState.is_authenticated, AppState.current_user_email, "Not signed in"),
                                font_size="0.7rem",
                                color=TEXT_MUTED,
                                class_name="sidebar-label",
                                max_width="135px",
                            ),
                            spacing="0",
                            align_items="flex-start",
                        ),
                        rx.spacer(),
                        # Action icon: Sign out if authenticated, Sign in if not
                        rx.cond(
                            AppState.is_authenticated,
                            neu_icon_button(
                                icon="log-out",
                                on_click=AppState.logout,
                                size=13,
                                tooltip="Sign out",
                            ),
                            neu_icon_button(
                                icon="log-in",
                                on_click=AppState.toggle_auth_dialog,
                                size=13,
                                tooltip="Sign in",
                            ),
                        ),
                        spacing="3",
                        align_items="center",
                        width="100%",
                    ),
                    padding="0.75rem",
                    border_radius=RADIUS_MD,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_RAISED_SM,
                    width="100%",
                ),
            ),
            spacing="3",
            height="100%",
            width="100%",
            align_items="flex-start",
        ),
        class_name=rx.cond(AppState.sidebar_collapsed, "app-sidebar collapsed", "app-sidebar"),
        height="100vh",
        position="sticky",
        top="0",
        padding="1.25rem 0.85rem",
        background_color=SURFACE_COLOR,
        border_right=f"1px solid var(--border-subtle)",
        box_shadow=f"2px 0 8px var(--shadow-dark)",
        flex_shrink=0,
        z_index="40",
    )
