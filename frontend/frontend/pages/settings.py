import reflex as rx
from frontend.components.layout import app_layout
from frontend.state import AppState

def settings_page() -> rx.Component:
    AppState.active_tab = "settings"
    return app_layout(
        "System Configuration",
        rx.vstack(
            rx.box(
                rx.vstack(
                    rx.text("LLM & Agent Configuration", font_size="1.1rem", font_weight="700", color="#ffffff"),
                    rx.text("Configure API keys, budget guardrails, and orchestration parameters.", font_size="0.85rem", color="#94a3b8"),
                    rx.divider(border_color="rgba(255, 255, 255, 0.08)"),
                    
                    rx.vstack(
                        rx.text("Anthropic Claude API Key", font_size="0.875rem", font_weight="600", color="#f1f5f9"),
                        rx.input(placeholder="sk-ant-api03-...", type="password", size="3", width="100%", variant="surface"),
                        rx.text("Used for Plan-Act-Reflect autonomous loop and natural language synthesis.", font_size="0.75rem", color="#64748b"),
                        spacing="1",
                        align_items="flex-start",
                        width="100%"
                    ),

                    rx.vstack(
                        rx.text("Per-Session Token Budget Cap", font_size="0.875rem", font_weight="600", color="#f1f5f9"),
                        rx.input(placeholder="50,000 tokens ($0.25 cap)", default_value="50000", size="3", width="100%", variant="surface"),
                        rx.text("Enforces strict safety guardrails preventing unbounded API calls (PRD Section 3.4).", font_size="0.75rem", color="#64748b"),
                        spacing="1",
                        align_items="flex-start",
                        width="100%"
                    ),

                    rx.vstack(
                        rx.text("Max Iteration Steps", font_size="0.875rem", font_weight="600", color="#f1f5f9"),
                        rx.input(placeholder="10 steps", default_value="10", size="3", width="100%", variant="surface"),
                        rx.text("Maximum tool invocations per analysis job.", font_size="0.75rem", color="#64748b"),
                        spacing="1",
                        align_items="flex-start",
                        width="100%"
                    ),

                    rx.button(
                        "Save Settings",
                        size="3",
                        variant="solid",
                        color_scheme="indigo"
                    ),

                    spacing="4",
                    align_items="flex-start",
                    width="100%"
                ),
                padding="1.5rem",
                border_radius="0.75rem",
                background_color="rgba(15, 23, 42, 0.6)",
                border="1px solid rgba(255, 255, 255, 0.08)",
                width="100%"
            ),
            spacing="5",
            width="100%"
        )
    )
