"""Run View / Execution Monitor page for Autonomous AI Data Analyst Agent.
Features a vertical 5-step timeline (Perceive -> Plan -> Act -> Reflect -> Synthesize),
active step opacity pulse, checkmark completions, budget gauges, and audit log.
"""
from typing import Any, Dict
import reflex as rx
from frontend.components.layout import app_layout
from frontend.components.neu_components import (
    empty_state,
    neu_button,
    neu_card,
    neu_inset_card,
    progress_track,
    status_pill,
)
from frontend.state import AppState, RunLogStepModel
from frontend.theme import (
    ACCENT_COLOR,
    ACCENT_SUBTLE,
    FONT_SERIF,
    RADIUS_FULL,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    SHADOW_INSET,
    SHADOW_RAISED,
    SHADOW_RAISED_SM,
    SURFACE_COLOR,
    TEXT_COLOR,
    TEXT_MUTED,
)


def timeline_step(
    step_num: int,
    step_title: str,
    step_description: str,
    is_done: rx.Var[bool],
    is_active: rx.Var[bool],
    is_last: bool = False,
) -> rx.Component:
    """A single vertical step in the 5-phase timeline with custom CSS animations."""
    indicator = rx.cond(
        is_done,
        # Completed: Solid accent circle with white checkmark and scale-in
        rx.box(
            rx.icon(tag="check", size=14, color="#ffffff"),
            class_name="neu-completed-step-check",
            width="28px",
            height="28px",
            border_radius=RADIUS_FULL,
            background_color=ACCENT_COLOR,
            box_shadow=SHADOW_RAISED_SM,
            display="flex",
            align_items="center",
            justify_content="center",
            flex_shrink=0,
        ),
        rx.cond(
            is_active,
            # Active: Terracotta border circle with slow opacity pulse (NO glow)
            rx.box(
                rx.box(
                    width="10px",
                    height="10px",
                    border_radius=RADIUS_FULL,
                    background_color=ACCENT_COLOR,
                ),
                class_name="neu-active-step-pulse",
                width="28px",
                height="28px",
                border_radius=RADIUS_FULL,
                background_color=SURFACE_COLOR,
                box_shadow=SHADOW_INSET,
                border=f"2px solid {ACCENT_COLOR}",
                display="flex",
                align_items="center",
                justify_content="center",
                flex_shrink=0,
            ),
            # Upcoming: Dim muted circle
            rx.box(
                rx.text(str(step_num), font_size="0.75rem", font_weight="600", color=TEXT_MUTED),
                width="28px",
                height="28px",
                border_radius=RADIUS_FULL,
                background_color=SURFACE_COLOR,
                box_shadow=SHADOW_INSET,
                display="flex",
                align_items="center",
                justify_content="center",
                flex_shrink=0,
            ),
        ),
    )

    vertical_line = rx.cond(
        not is_last,
        rx.box(
            width="2px",
            flex_grow="1",
            min_height="32px",
            background_color=rx.cond(is_done, ACCENT_COLOR, "var(--shadow-light)"),
            margin_y="4px",
        ),
        rx.box(),
    )

    return rx.hstack(
        # Left column: Indicator icon + connector vertical line
        rx.vstack(
            indicator,
            vertical_line,
            align_items="center",
            spacing="0",
            flex_shrink=0,
        ),
        # Right column: Step content
        rx.vstack(
            rx.hstack(
                rx.text(
                    step_title,
                    font_size="0.95rem",
                    font_weight=rx.cond(is_active | is_done, "600", "500"),
                    color=rx.cond(is_active | is_done, TEXT_COLOR, TEXT_MUTED),
                ),
                rx.cond(
                    is_active,
                    status_pill("In Progress", icon="activity", status="info"),
                ),
                rx.cond(
                    is_done,
                    rx.text("Complete", font_size="0.72rem", color="var(--status-success)", font_weight="500"),
                ),
                spacing="2",
                align_items="center",
            ),
            rx.text(
                step_description,
                font_size="0.825rem",
                color=TEXT_MUTED,
                line_height="1.45",
            ),
            # If this is the active phase, display current step details
            rx.cond(
                is_active & (AppState.job_current_step_name != ""),
                neu_inset_card(
                    rx.hstack(
                        rx.icon(tag="terminal", size=13, color=ACCENT_COLOR),
                        rx.text(
                            AppState.job_current_step_name,
                            font_size="0.775rem",
                            color=TEXT_COLOR,
                            font_family="monospace",
                        ),
                        spacing="2",
                        align_items="center",
                    ),
                    padding="0.5rem 0.85rem",
                    width="100%",
                    margin_top="0.35rem",
                ),
            ),
            spacing="1",
            align_items="flex-start",
            padding_bottom="1.5rem",
            width="100%",
        ),
        spacing="3",
        align_items="flex-start",
        width="100%",
    )


def run_log_step_row(step: RunLogStepModel) -> rx.Component:
    """Row displaying an individual step's rationale, tool, latency, and tokens."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.text(f"#{step.step}", font_size="0.72rem", font_weight="700", color=ACCENT_COLOR),
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_RAISED_SM,
                    padding="0.15rem 0.45rem",
                    border_radius=RADIUS_SM,
                ),
                rx.text(step.tool, font_size="0.8rem", font_weight="600", color=TEXT_COLOR),
                rx.spacer(),
                rx.hstack(
                    rx.icon(tag="clock", size=11, color=TEXT_MUTED),
                    rx.text(f"{step.tool_time_ms:.1f}ms tool", font_size="0.7rem", color=TEXT_MUTED),
                    rx.text(f"+ {step.llm_latency_ms:.1f}ms llm", font_size="0.7rem", color=TEXT_MUTED),
                    spacing="1",
                    align_items="center",
                ),
                rx.box(
                    rx.text(f"{step.tokens} tokens", font_size="0.7rem", color=TEXT_MUTED),
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_INSET,
                    padding="0.15rem 0.4rem",
                    border_radius=RADIUS_SM,
                ),
                spacing="2",
                align_items="center",
                width="100%",
            ),
            rx.cond(
                step.rationale != "",
                rx.text(
                    step.rationale,
                    font_size="0.78rem",
                    color=TEXT_MUTED,
                    line_height="1.4",
                ),
            ),
            spacing="1",
            align_items="flex-start",
            width="100%",
        ),
        padding="0.75rem 0.9rem",
        border_radius=RADIUS_MD,
        background_color=SURFACE_COLOR,
        box_shadow=SHADOW_INSET,
        width="100%",
    )


def run_page() -> rx.Component:
    """Agent Execution Monitor & Progress Timeline view."""
    return app_layout(
        "Run Monitor",
        rx.vstack(
            # 1. Header Information Card
            neu_card(
                rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.hstack(
                                rx.icon(tag="cpu", size=18, color=ACCENT_COLOR),
                                rx.text("Autonomous Agent Monitor", font_size="1.1rem", font_weight="600", color=TEXT_COLOR),
                                rx.cond(
                                    AppState.job_status == "running",
                                    status_pill("Active Execution", icon="activity", status="info"),
                                    rx.cond(
                                        AppState.job_status == "completed",
                                        status_pill("Completed", icon="circle-check", status="success"),
                                        rx.cond(
                                            AppState.job_status == "budget_tripped",
                                            status_pill("Budget Tripped", icon="shield-alert", status="warn"),
                                            status_pill(AppState.job_status, icon="circle-alert", status="error"),
                                        ),
                                    ),
                                ),
                                spacing="2",
                                align_items="center",
                            ),
                            rx.hstack(
                                rx.text(
                                    f"Dataset: {AppState.selected_dataset_name}",
                                    font_size="0.825rem",
                                    color=TEXT_MUTED,
                                ),
                                rx.text("•", color=TEXT_MUTED),
                                rx.text(
                                    f"Job ID: {AppState.active_job_id}",
                                    font_size="0.75rem",
                                    color=TEXT_MUTED,
                                    font_family="monospace",
                                ),
                                spacing="2",
                                align_items="center",
                            ),
                            spacing="1",
                            align_items="flex-start",
                        ),
                        rx.spacer(),
                        # Action Buttons
                        rx.hstack(
                            rx.cond(
                                AppState.job_status == "failed",
                                neu_button(
                                    rx.hstack(
                                        rx.icon(tag="rotate-cw", size=14),
                                        rx.text("Retry Analysis"),
                                        spacing="1",
                                        align_items="center",
                                    ),
                                    variant="primary",
                                    on_click=AppState.retry_job,
                                ),
                            ),
                            rx.cond(
                                (AppState.job_status == "completed") | (AppState.job_status == "budget_tripped"),
                                rx.link(
                                    neu_button(
                                        rx.hstack(
                                            rx.icon(tag="layout-dashboard", size=14),
                                            rx.text("View Dashboard"),
                                            spacing="1",
                                            align_items="center",
                                        ),
                                        variant="primary",
                                    ),
                                    href="/dashboard",
                                    text_decoration="none",
                                ),
                            ),
                            rx.link(
                                neu_button(
                                    rx.hstack(
                                        rx.icon(tag="message-square", size=14),
                                        rx.text("Ask in Chat"),
                                        spacing="1",
                                        align_items="center",
                                    ),
                                    variant="secondary",
                                ),
                                href="/chat",
                                text_decoration="none",
                            ),
                            spacing="2",
                            align_items="center",
                        ),
                        width="100%",
                        align_items="center",
                    ),
                    # Goal quote if present
                    rx.cond(
                        AppState.analysis_goal != "",
                        neu_inset_card(
                            rx.hstack(
                                rx.icon(tag="target", size=14, color=ACCENT_COLOR),
                                rx.text(f"Goal: {AppState.analysis_goal}", font_size="0.825rem", color=TEXT_COLOR, font_style="italic"),
                                spacing="2",
                                align_items="center",
                            ),
                            padding="0.65rem 0.9rem",
                            width="100%",
                        ),
                    ),
                    spacing="3",
                    align_items="flex-start",
                    width="100%",
                ),
                width="100%",
            ),

            # 2. Budget Tripped Alert (Guaranteed deterministic termination without overbilling)
            rx.cond(
                AppState.is_budget_tripped,
                neu_card(
                    rx.hstack(
                        rx.box(
                            rx.icon(tag="shield-alert", size=22, color="var(--status-warning)"),
                            padding="0.6rem",
                            border_radius=RADIUS_FULL,
                            background_color=SURFACE_COLOR,
                            box_shadow=SHADOW_INSET,
                            flex_shrink=0,
                        ),
                        rx.vstack(
                            rx.text("Token Safety Budget Reached", font_size="0.95rem", font_weight="600", color=TEXT_COLOR),
                            rx.text(
                                f"The run consumed {AppState.job_tokens_used} tokens, reaching the safety cap of {AppState.job_token_budget} tokens. "
                                "The agent halted further exploratory LLM tool calls and invoked deterministic heuristic synthesis. "
                                "All findings remain factually grounded.",
                                font_size="0.825rem",
                                color=TEXT_MUTED,
                                line_height="1.45",
                            ),
                            spacing="1",
                            align_items="flex-start",
                        ),
                        spacing="3",
                        align_items="flex-start",
                        width="100%",
                    ),
                    width="100%",
                ),
            ),

            # 3. Execution Gauges Grid (Tokens, Steps, Latency)
            rx.grid(
                neu_card(
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="coins", size=16, color=ACCENT_COLOR),
                            rx.text("Token Consumption", font_size="0.8rem", color=TEXT_MUTED),
                            rx.spacer(),
                            rx.text(f"{AppState.job_tokens_used} / {AppState.job_token_budget}", font_size="0.8rem", font_weight="600", color=TEXT_COLOR),
                            width="100%",
                            align_items="center",
                        ),
                        progress_track(percent=AppState.token_budget_pct, height="6px"),
                        spacing="2",
                        width="100%",
                    ),
                    sm=True,
                    width="100%",
                ),
                neu_card(
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="layers", size=16, color=ACCENT_COLOR),
                            rx.text("Step Progress", font_size="0.8rem", color=TEXT_MUTED),
                            rx.spacer(),
                            rx.text(f"Step {AppState.job_current_step} of {AppState.job_step_limit}", font_size="0.8rem", font_weight="600", color=TEXT_COLOR),
                            width="100%",
                            align_items="center",
                        ),
                        progress_track(percent=AppState.job_progress_pct, height="6px"),
                        spacing="2",
                        width="100%",
                    ),
                    sm=True,
                    width="100%",
                ),
                neu_card(
                    rx.vstack(
                        rx.hstack(
                            rx.icon(tag="timer", size=16, color=ACCENT_COLOR),
                            rx.text("Execution Time", font_size="0.8rem", color=TEXT_MUTED),
                            rx.spacer(),
                            rx.text(f"{AppState.job_elapsed_seconds:.1f}s", font_size="0.85rem", font_weight="700", color=TEXT_COLOR),
                            width="100%",
                            align_items="center",
                        ),
                        rx.text("Autonomous latency tracking", font_size="0.75rem", color=TEXT_MUTED),
                        spacing="2",
                        width="100%",
                    ),
                    sm=True,
                    width="100%",
                ),
                columns=rx.breakpoints(initial="1", sm="3"),
                spacing="3",
                width="100%",
            ),

            # 4. Vertical 5-Step Timeline
            neu_card(
                rx.vstack(
                    rx.hstack(
                        rx.icon(tag="git-commit-vertical", size=18, color=ACCENT_COLOR),
                        rx.text("Autonomous Execution Pipeline", font_size="1rem", font_weight="600", color=TEXT_COLOR),
                        rx.spacer(),
                        rx.text("5-Phase Loop", font_size="0.75rem", color=TEXT_MUTED),
                        width="100%",
                        align_items="center",
                    ),
                    rx.box(
                        rx.vstack(
                            timeline_step(
                                step_num=1,
                                step_title="1. Perceive",
                                step_description="Ingest normalized dataset, parse structural shapes, infer column data types, and run baseline statistical profiling.",
                                is_done=AppState.is_perceive_done,
                                is_active=AppState.is_perceive_active,
                            ),
                            timeline_step(
                                step_num=2,
                                step_title="2. Plan",
                                step_description="Formulate prioritized analytical hypotheses, inspect correlation matrices, and select deterministic statistical tool candidates.",
                                is_done=AppState.is_plan_done,
                                is_active=AppState.is_plan_active,
                            ),
                            timeline_step(
                                step_num=3,
                                step_title="3. Act",
                                step_description="Execute targeted tools (segment comparisons, trend analysis, bivariate distributions, anomaly detection) with strict token budgets.",
                                is_done=AppState.is_act_done,
                                is_active=AppState.is_act_active,
                            ),
                            timeline_step(
                                step_num=4,
                                step_title="4. Reflect",
                                step_description="Evaluate p-values, measure effect sizes (Cohen's d), quantify sample coverage exclusions, and compile statistical caveats.",
                                is_done=AppState.is_reflect_done,
                                is_active=AppState.is_reflect_active,
                            ),
                            timeline_step(
                                step_num=5,
                                step_title="5. Synthesize",
                                step_description="Generate executive narrative summary, assemble publication-ready chart specifications, and verify every factual citation.",
                                is_done=AppState.is_synth_done,
                                is_active=AppState.is_synth_active,
                                is_last=True,
                            ),
                            spacing="0",
                            width="100%",
                        ),
                        padding_top="1rem",
                        width="100%",
                    ),
                    spacing="3",
                    align_items="flex-start",
                    width="100%",
                ),
                width="100%",
            ),

            # 5. Expandable Run Log & Explainability Panel
            neu_card(
                rx.vstack(
                    rx.hstack(
                        rx.hstack(
                            rx.icon(tag="file-code", size=18, color=ACCENT_COLOR),
                            rx.text("Explainability & Tool Audit Trail", font_size="1rem", font_weight="600", color=TEXT_COLOR),
                            spacing="2",
                            align_items="center",
                        ),
                        rx.spacer(),
                        rx.text(
                            f"{AppState.job_run_log.length()} steps executed",
                            font_size="0.8rem",
                            color=TEXT_MUTED,
                        ),
                        width="100%",
                        align_items="center",
                    ),
                    rx.text(
                        "Every autonomous decision, LLM rationale, deterministic tool call, and latency breakdown.",
                        font_size="0.825rem",
                        color=TEXT_MUTED,
                    ),
                    # List of run log items or empty state
                    rx.cond(
                        AppState.job_run_log.length() > 0,
                        rx.vstack(
                            rx.foreach(AppState.job_run_log, run_log_step_row),
                            spacing="2",
                            width="100%",
                        ),
                        empty_state(
                            title="No Execution Steps Recorded Yet",
                            description="Run logs will appear sequentially as the agent plans and executes statistical analysis tools.",
                            icon="list-checks",
                        ),
                    ),
                    spacing="3",
                    align_items="flex-start",
                    width="100%",
                ),
                width="100%",
            ),

            spacing="4",
            width="100%",
        ),
    )
