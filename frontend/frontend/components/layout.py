import reflex as rx
from frontend.state import AppState

def nav_item(label: str, icon: str, route: str, current_tab: str) -> rx.Component:
    is_active = (current_tab == label.lower())
    return rx.link(
        rx.hstack(
            rx.icon(tag=icon, size=18, color=rx.cond(is_active, "#818cf8", "#94a3b8")),
            rx.text(
                label,
                font_weight=rx.cond(is_active, "600", "400"),
                color=rx.cond(is_active, "#ffffff", "#94a3b8"),
                font_size="0.925rem"
            ),
            spacing="3",
            align_items="center",
            padding_y="0.65rem",
            padding_x="0.85rem",
            border_radius="0.5rem",
            background_color=rx.cond(is_active, "rgba(99, 102, 241, 0.15)", "transparent"),
            border=rx.cond(is_active, "1px solid rgba(99, 102, 241, 0.3)", "1px solid transparent"),
            _hover={"background_color": "rgba(255, 255, 255, 0.05)"},
            transition="all 0.15s ease-in-out",
            width="100%"
        ),
        href=route,
        text_decoration="none",
        width="100%"
    )

def sidebar() -> rx.Component:
    return rx.vstack(
        # App Branding
        rx.hstack(
            rx.box(
                rx.icon(tag="bot", size=22, color="#ffffff"),
                padding="0.5rem",
                border_radius="0.6rem",
                background="linear-gradient(135deg, #6366f1 0%, #a855f7 100%)",
                box_shadow="0 4px 12px rgba(99, 102, 241, 0.3)"
            ),
            rx.vstack(
                rx.text("AutoAnalyst", font_size="1.1rem", font_weight="700", color="#ffffff", line_height="1.2"),
                rx.text("Autonomous AI Agent", font_size="0.75rem", color="#818cf8"),
                spacing="0",
                align_items="flex-start"
            ),
            spacing="3",
            align_items="center",
            padding_bottom="1.5rem",
            border_bottom="1px solid rgba(255, 255, 255, 0.08)",
            width="100%"
        ),
        
        # Navigation Menu
        rx.vstack(
            rx.text("CORE PIPELINE", font_size="0.68rem", font_weight="700", color="#64748b", letter_spacing="0.08em"),
            nav_item("Upload", "upload", "/upload", AppState.active_tab),
            nav_item("Dashboard", "layout-dashboard", "/dashboard", AppState.active_tab),
            nav_item("Chat", "message-square", "/chat", AppState.active_tab),
            nav_item("Reports", "file-text", "/reports", AppState.active_tab),
            rx.divider(border_color="rgba(255, 255, 255, 0.08)", margin_y="0.75rem"),
            rx.text("CONFIGURATION", font_size="0.68rem", font_weight="700", color="#64748b", letter_spacing="0.08em"),
            nav_item("Settings", "settings", "/settings", AppState.active_tab),
            spacing="1",
            width="100%",
            align_items="flex-start"
        ),
        
        rx.spacer(),
        
        # Selected Dataset Pill
        rx.box(
            rx.vstack(
                rx.hstack(
                    rx.box(width="8px", height="8px", border_radius="50%", background_color="#10b981"),
                    rx.text("Active Dataset", font_size="0.75rem", color="#94a3b8"),
                    spacing="2",
                    align_items="center"
                ),
                rx.text(
                    AppState.selected_dataset_name,
                    font_size="0.825rem",
                    font_weight="600",
                    color="#f1f5f9",
                    is_truncated=True,
                    max_width="180px"
                ),
                align_items="flex-start",
                spacing="1"
            ),
            padding="0.75rem",
            border_radius="0.6rem",
            background_color="rgba(15, 23, 42, 0.6)",
            border="1px solid rgba(255, 255, 255, 0.08)",
            width="100%"
        ),
        
        width="260px",
        height="100vh",
        position="sticky",
        top="0",
        padding="1.5rem",
        background_color="#0b0f19",
        border_right="1px solid rgba(255, 255, 255, 0.08)",
        align_items="flex-start"
    )

def top_header(page_title: str) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(page_title, font_size="1.4rem", font_weight="700", color="#ffffff"),
            rx.text("Autonomous data ingestion, cleaning & deterministic profiling", font_size="0.825rem", color="#94a3b8"),
            spacing="0",
            align_items="flex-start"
        ),
        rx.spacer(),
        rx.hstack(
            rx.badge("Phase 1 Active", color_scheme="indigo", variant="surface"),
            rx.button(
                rx.hstack(
                    rx.icon(tag="refresh-cw", size=14),
                    rx.text("Refresh"),
                    spacing="2",
                    align_items="center"
                ),
                size="2",
                variant="soft",
                color_scheme="gray",
                on_click=AppState.fetch_datasets
            ),
            spacing="3",
            align_items="center"
        ),
        width="100%",
        padding_y="1rem",
        padding_x="2rem",
        border_bottom="1px solid rgba(255, 255, 255, 0.06)",
        background_color="rgba(11, 15, 25, 0.8)",
        backdrop_filter="blur(12px)",
        position="sticky",
        top="0",
        z_index="50"
    )

def app_layout(page_title: str, content: rx.Component) -> rx.Component:
    """Wraps page content in the standard app shell with sidebar and top header."""
    return rx.hstack(
        sidebar(),
        rx.vstack(
            top_header(page_title),
            rx.box(
                content,
                padding="2rem",
                width="100%",
                max_width="1400px",
                margin="0 auto"
            ),
            width="calc(100vw - 260px)",
            min_height="100vh",
            background_color="#070a11",
            spacing="0",
            overflow_y="auto"
        ),
        spacing="0",
        width="100vw",
        min_height="100vh",
        background_color="#070a11",
        color="#f8fafc",
        font_family="'Inter', sans-serif"
    )
