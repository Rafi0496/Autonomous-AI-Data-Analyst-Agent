"""System Configuration & Settings page for Autonomous AI Data Analyst Agent (Milestone 3)."""
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
                    rx.hstack(
                        rx.icon(tag="sliders-horizontal", size=20, color="#818cf8"),
                        rx.text("Active LLM & Execution Configuration", font_size="1.1rem", font_weight="700", color="#ffffff"),
                        spacing="2",
                        align_items="center"
                    ),
                    rx.text(
                        "Runtime orchestration parameters, active provider models, and safety budget guardrails.",
                        font_size="0.85rem",
                        color="#94a3b8"
                    ),
                    rx.divider(border_color="rgba(255, 255, 255, 0.08)"),
                    
                    # LLM Provider info
                    rx.grid(
                        rx.box(
                            rx.vstack(
                                rx.text("Active LLM Provider", font_size="0.8rem", font_weight="600", color="#94a3b8"),
                                rx.hstack(
                                    rx.badge(AppState.active_provider.upper(), color_scheme="indigo", variant="solid", size="2"),
                                    rx.text("Provider-Agnostic Interface", font_size="0.75rem", color="#64748b"),
                                    spacing="2",
                                    align_items="center"
                                ),
                                rx.text("Configured via LLM_PROVIDER in .env (gemini | claude | heuristic).", font_size="0.75rem", color="#64748b"),
                                spacing="2",
                                align_items="flex-start"
                            ),
                            padding="1.25rem",
                            border_radius="0.5rem",
                            background_color="rgba(30, 41, 59, 0.4)",
                            border="1px solid rgba(255, 255, 255, 0.05)"
                        ),
                        rx.box(
                            rx.vstack(
                                rx.text("Active Model", font_size="0.8rem", font_weight="600", color="#94a3b8"),
                                rx.badge(AppState.active_model, color_scheme="blue", variant="surface", size="2"),
                                rx.text("Used for Plan-Act-Reflect orchestration and synthesis.", font_size="0.75rem", color="#64748b"),
                                spacing="2",
                                align_items="flex-start"
                            ),
                            padding="1.25rem",
                            border_radius="0.5rem",
                            background_color="rgba(30, 41, 59, 0.4)",
                            border="1px solid rgba(255, 255, 255, 0.05)"
                        ),
                        columns=rx.breakpoints(initial="1", sm="2"),
                        spacing="3",
                        width="100%"
                    ),

                    # Safety Budgets
                    rx.grid(
                        rx.box(
                            rx.vstack(
                                rx.text("Step Budget Cap", font_size="0.8rem", font_weight="600", color="#94a3b8"),
                                rx.hstack(
                                    rx.badge(f"{AppState.step_budget_setting} Max Steps", color_scheme="amber", variant="solid", size="2"),
                                    rx.text("Guardrail limit", font_size="0.75rem", color="#64748b"),
                                    spacing="2",
                                    align_items="center"
                                ),
                                rx.text("Hard limit preventing infinite autonomous tool call loops.", font_size="0.75rem", color="#64748b"),
                                spacing="2",
                                align_items="flex-start"
                            ),
                            padding="1.25rem",
                            border_radius="0.5rem",
                            background_color="rgba(30, 41, 59, 0.4)",
                            border="1px solid rgba(255, 255, 255, 0.05)"
                        ),
                        rx.box(
                            rx.vstack(
                                rx.text("Token Budget Cap", font_size="0.8rem", font_weight="600", color="#94a3b8"),
                                rx.hstack(
                                    rx.badge(f"{AppState.token_budget_setting} Tokens", color_scheme="purple", variant="solid", size="2"),
                                    rx.text("Cost protection", font_size="0.75rem", color="#64748b"),
                                    spacing="2",
                                    align_items="center"
                                ),
                                rx.text("Strict safety guardrail halting execution if token usage exceeds cap.", font_size="0.75rem", color="#64748b"),
                                spacing="2",
                                align_items="flex-start"
                            ),
                            padding="1.25rem",
                            border_radius="0.5rem",
                            background_color="rgba(30, 41, 59, 0.4)",
                            border="1px solid rgba(255, 255, 255, 0.05)"
                        ),
                        columns=rx.breakpoints(initial="1", sm="2"),
                        spacing="3",
                        width="100%"
                    ),

                    # Stack info
                    rx.box(
                        rx.vstack(
                            rx.text("Stack Architecture", font_size="0.85rem", font_weight="600", color="#f1f5f9"),
                            rx.text("Backend: FastAPI + Celery Async Task Queue with Redis / In-memory backend", font_size="0.8rem", color="#94a3b8"),
                            rx.text("Frontend: Pure Python Reflex Reactive Web App", font_size="0.8rem", color="#94a3b8"),
                            rx.text("Reporting: ReportLab (PDF) & python-docx (Word) headless generators", font_size="0.8rem", color="#94a3b8"),
                            rx.text("Visualization: Headless Matplotlib + Reflex Recharts", font_size="0.8rem", color="#94a3b8"),
                            spacing="1",
                            align_items="flex-start"
                        ),
                        padding="1.25rem",
                        border_radius="0.5rem",
                        background_color="rgba(15, 23, 42, 0.4)",
                        border="1px solid rgba(255, 255, 255, 0.05)",
                        width="100%"
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
