"""Landing Page for AutoAnalyst: Professional Project Overview, Complete Feature Showcase, Quick Dataset Upload, and Get Started Entry."""
from typing import Any, Dict
import reflex as rx
from frontend.components.layout import landing_layout
from frontend.components.neu_components import (
    empty_state,
    neu_button,
    neu_card,
    status_pill,
)
from frontend.state import AppState, RecentJobModel
from frontend.theme import (
    ACCENT_COLOR,
    ACCENT_HOVER,
    FONT_SERIF,
    RADIUS_FULL,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    RADIUS_XL,
    SHADOW_INSET,
    SHADOW_RAISED,
    SHADOW_RAISED_SM,
    SURFACE_COLOR,
    TEXT_COLOR,
    TEXT_MUTED,
)


def feature_card(icon: str, title: str, description: str, badges: list[str]) -> rx.Component:
    """Rich Neumorphic feature showcase card with icon, title, description, and capability tags."""
    return neu_card(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.icon(tag=icon, size=20, color=ACCENT_COLOR),
                    padding="0.65rem",
                    border_radius=RADIUS_MD,
                    background_color=SURFACE_COLOR,
                    box_shadow=SHADOW_RAISED_SM,
                ),
                rx.text(
                    title,
                    font_size="1.05rem",
                    font_weight="700",
                    color=TEXT_COLOR,
                    letter_spacing="-0.01em",
                ),
                spacing="3",
                align_items="center",
            ),
            rx.text(
                description,
                font_size="0.85rem",
                color=TEXT_MUTED,
                line_height="1.6",
            ),
            rx.hstack(
                *[
                    rx.box(
                        rx.text(b, font_size="0.7rem", font_weight="500", color=TEXT_COLOR),
                        padding="0.2rem 0.55rem",
                        border_radius=RADIUS_FULL,
                        background_color=SURFACE_COLOR,
                        box_shadow=SHADOW_INSET,
                    )
                    for b in badges
                ],
                spacing="2",
                wrap="wrap",
                margin_top="0.5rem",
            ),
            spacing="3",
            align_items="flex-start",
            height="100%",
            justify_content="space-between",
        ),
        class_name="landing-feature-card",
        padding="1.5rem",
        width="100%",
    )


def pipeline_step(step_num: str, title: str, subtitle: str, description: str, icon: str) -> rx.Component:
    """Pipeline flow card with numbered badge and clear process description."""
    return neu_card(
        rx.vstack(
            rx.hstack(
                rx.box(
                    rx.text(step_num, font_weight="700", font_size="0.85rem", color="#FFFFFF"),
                    class_name="pipeline-step-badge",
                ),
                rx.vstack(
                    rx.text(title, font_size="0.95rem", font_weight="700", color=TEXT_COLOR),
                    rx.text(subtitle, font_size="0.75rem", font_weight="500", color=ACCENT_COLOR),
                    spacing="0",
                    align_items="flex-start",
                ),
                rx.spacer(),
                rx.icon(tag=icon, size=18, color=TEXT_MUTED),
                width="100%",
                align_items="center",
            ),
            rx.text(
                description,
                font_size="0.825rem",
                color=TEXT_MUTED,
                line_height="1.55",
            ),
            spacing="3",
            align_items="flex-start",
            width="100%",
        ),
        padding="1.25rem",
        width="100%",
    )


def benchmark_launcher_card(name: str, file_name: str, rows_cols: str, description: str, icon: str) -> rx.Component:
    """Quick launcher card for preloaded industry benchmark datasets."""
    return rx.box(
        neu_card(
            rx.vstack(
                rx.hstack(
                    rx.box(
                        rx.icon(tag=icon, size=18, color=ACCENT_COLOR),
                        padding="0.5rem",
                        border_radius=RADIUS_MD,
                        background_color=SURFACE_COLOR,
                        box_shadow=SHADOW_RAISED_SM,
                    ),
                    rx.vstack(
                        rx.text(name, font_size="0.9rem", font_weight="700", color=TEXT_COLOR),
                        rx.text(rows_cols, font_size="0.72rem", color=TEXT_MUTED, font_weight="500"),
                        spacing="0",
                        align_items="flex-start",
                    ),
                    rx.spacer(),
                    rx.icon(tag="arrow-up-right", size=15, color=TEXT_MUTED),
                    width="100%",
                    align_items="center",
                ),
                rx.text(
                    description,
                    font_size="0.775rem",
                    color=TEXT_MUTED,
                    line_height="1.45",
                ),
                rx.hstack(
                    rx.text("Click to load & launch", font_size="0.72rem", color=ACCENT_COLOR, font_weight="600"),
                    rx.icon(tag="play", size=11, color=ACCENT_COLOR),
                    spacing="1",
                    align_items="center",
                    margin_top="0.25rem",
                ),
                spacing="2",
                align_items="flex-start",
                width="100%",
            ),
            padding="1.15rem",
            width="100%",
        ),
        class_name="landing-benchmark-card",
        on_click=AppState.quick_start_benchmark(file_name),
        width="100%",
    )


def home_page() -> rx.Component:
    """Complete, Professional Landing Page for AutoAnalyst."""
    return landing_layout(
        rx.vstack(
            # =========================================================
            # 1. HERO SECTION (Brand headline, badge, value prop, CTAs)
            # =========================================================
            rx.vstack(
                # Pill Badge
                rx.box(
                    rx.hstack(
                        rx.icon(tag="sparkles", size=13, color=ACCENT_COLOR),
                        rx.text("AUTONOMOUS STATISTICAL AI AGENT • FACT-GROUNDED INTELLIGENCE", font_size="0.75rem"),
                        spacing="2",
                        align_items="center",
                    ),
                    class_name="landing-badge-pill",
                    margin_bottom="1.25rem",
                ),

                # Main Hero Headline
                rx.text(
                    "Autonomous AI Data Analyst",
                    font_family=FONT_SERIF,
                    font_size=rx.breakpoints(initial="2.4rem", sm="3.4rem", md="4rem"),
                    font_weight="400",
                    color=TEXT_COLOR,
                    letter_spacing="-0.03em",
                    text_align="center",
                    line_height="1.1",
                    max_width="850px",
                    class_name="landing-hero-title",
                ),

                # Subheadline
                rx.text(
                    "From raw CSV to deterministic data cleaning, automated statistical hypothesis testing, interactive dashboards, and publication-ready audit reports in seconds.",
                    font_size=rx.breakpoints(initial="0.95rem", sm="1.1rem"),
                    color=TEXT_MUTED,
                    text_align="center",
                    max_width="660px",
                    line_height="1.6",
                    margin_top="1rem",
                    class_name="landing-hero-subtitle",
                ),

                # Dual Call To Action Buttons
                rx.hstack(
                    # Primary "Get Started" Button -> Enters Operational Workspace
                    rx.link(
                        neu_button(
                            rx.hstack(
                                rx.text("Get Started", font_weight="600", font_size="0.95rem"),
                                rx.icon(tag="arrow-right", size=16),
                                spacing="2",
                                align_items="center",
                            ),
                            variant="primary",
                            padding="0.8rem 1.85rem",
                            border_radius=RADIUS_MD,
                        ),
                        href="/upload",
                        text_decoration="none",
                    ),

                    # Secondary "Upload Dataset" Button -> Jumps to Upload Dropzone
                    rx.link(
                        neu_button(
                            rx.hstack(
                                rx.icon(tag="upload", size=16),
                                rx.text("Upload Dataset", font_weight="600", font_size="0.95rem"),
                                spacing="2",
                                align_items="center",
                            ),
                            variant="secondary",
                            padding="0.8rem 1.75rem",
                            border_radius=RADIUS_MD,
                        ),
                        href="#upload-section",
                        text_decoration="none",
                    ),
                    spacing="3",
                    align_items="center",
                    justify="center",
                    margin_top="1.85rem",
                    wrap="wrap",
                    class_name="landing-hero-cta",
                ),

                # Trust badges row
                rx.hstack(
                    rx.hstack(
                        rx.icon(tag="shield-check", size=14, color=ACCENT_COLOR),
                        rx.text("100% Citation Grounded", font_size="0.775rem", color=TEXT_MUTED, font_weight="500"),
                        spacing="1",
                        align_items="center",
                    ),
                    rx.hstack(
                        rx.icon(tag="zap", size=14, color=ACCENT_COLOR),
                        rx.text("< 3s Compute", font_size="0.775rem", color=TEXT_MUTED, font_weight="500"),
                        spacing="1",
                        align_items="center",
                    ),
                    rx.hstack(
                        rx.icon(tag="database", size=14, color=ACCENT_COLOR),
                        rx.text("Deterministic Sanitization", font_size="0.775rem", color=TEXT_MUTED, font_weight="500"),
                        spacing="1",
                        align_items="center",
                    ),
                    rx.hstack(
                        rx.icon(tag="file-text", size=14, color=ACCENT_COLOR),
                        rx.text("Audit-Ready PDF Reports", font_size="0.775rem", color=TEXT_MUTED, font_weight="500"),
                        spacing="1",
                        align_items="center",
                    ),
                    spacing="4",
                    align_items="center",
                    justify="center",
                    wrap="wrap",
                    margin_top="2.25rem",
                    class_name="landing-trust-bar",
                ),

                spacing="0",
                align_items="center",
                width="100%",
                padding_top=rx.breakpoints(initial="2rem", sm="3.5rem"),
                padding_bottom="3rem",
            ),

            # =========================================================
            # 2. UPLOAD DATASET & BENCHMARK LAUNCHER (id="upload-section")
            # =========================================================
            rx.vstack(
                rx.vstack(
                    rx.text(
                        "DATASET INGESTION",
                        font_size="0.75rem",
                        font_weight="700",
                        color=ACCENT_COLOR,
                        letter_spacing="0.1em",
                    ),
                    rx.text(
                        "Upload Your Dataset to Begin",
                        font_family=FONT_SERIF,
                        font_size=rx.breakpoints(initial="1.6rem", sm="2.1rem"),
                        font_weight="400",
                        color=TEXT_COLOR,
                        letter_spacing="-0.02em",
                    ),
                    rx.text(
                        "Upload a CSV or Excel file to automatically sanitize sentinels, generate statistical profiles, and enter the operational workspace.",
                        font_size="0.9rem",
                        color=TEXT_MUTED,
                        text_align="center",
                        max_width="600px",
                        line_height="1.5",
                    ),
                    spacing="1",
                    align_items="center",
                    width="100%",
                    margin_bottom="1.5rem",
                ),

                # Large Neumorphic Ingestion Card
                neu_card(
                    rx.vstack(
                        # File Dropzone Area
                        rx.upload(
                            rx.vstack(
                                rx.box(
                                    rx.icon(tag="cloud-upload", size=32, color=ACCENT_COLOR),
                                    padding="1rem",
                                    border_radius=RADIUS_FULL,
                                    background_color=SURFACE_COLOR,
                                    box_shadow=SHADOW_RAISED_SM,
                                ),
                                rx.text(
                                    "Drop your CSV file here, or click to browse",
                                    font_size="1rem",
                                    font_weight="600",
                                    color=TEXT_COLOR,
                                ),
                                rx.text(
                                    "Supports CSV, TSV, and XLSX up to 50MB • Automatic type inference & sentinel filtering",
                                    font_size="0.8rem",
                                    color=TEXT_MUTED,
                                ),
                                spacing="2",
                                align_items="center",
                                justify="center",
                                padding="2.5rem 1.5rem",
                                width="100%",
                            ),
                            id="landing_dataset_upload",
                            border=f"2px dashed var(--border-subtle)",
                            border_radius=RADIUS_MD,
                            background_color=SURFACE_COLOR,
                            box_shadow=SHADOW_INSET,
                            cursor="pointer",
                            width="100%",
                            _hover={"border_color": ACCENT_COLOR},
                            transition="border-color 150ms ease",
                        ),

                        # Action row below upload box
                        rx.hstack(
                            rx.hstack(
                                rx.icon(tag="info", size=14, color=TEXT_MUTED),
                                rx.text(
                                    "Ready to inspect raw columns, detect invalid sentinels, and run full statistical tests.",
                                    font_size="0.775rem",
                                    color=TEXT_MUTED,
                                ),
                                spacing="2",
                                align_items="center",
                            ),
                            rx.spacer(),
                            rx.link(
                                neu_button(
                                    rx.hstack(
                                        rx.text("Enter Datasets Workspace", font_weight="600", font_size="0.85rem"),
                                        rx.icon(tag="arrow-right", size=14),
                                        spacing="2",
                                        align_items="center",
                                    ),
                                    variant="primary",
                                    padding="0.6rem 1.25rem",
                                ),
                                href="/upload",
                                text_decoration="none",
                            ),
                            width="100%",
                            align_items="center",
                            wrap="wrap",
                            spacing="3",
                        ),

                        # Divider
                        rx.box(
                            width="100%",
                            height="1px",
                            background_color="var(--border-subtle)",
                            margin_y="1rem",
                        ),

                        # Or try benchmark datasets section
                        rx.vstack(
                            rx.hstack(
                                rx.icon(tag="sparkles", size=15, color=ACCENT_COLOR),
                                rx.text(
                                    "OR LAUNCH A PRELOADED BENCHMARK DATASET (1-CLICK TEST)",
                                    font_size="0.75rem",
                                    font_weight="700",
                                    color=TEXT_MUTED,
                                    letter_spacing="0.06em",
                                ),
                                spacing="2",
                                align_items="center",
                            ),
                            rx.grid(
                                benchmark_launcher_card(
                                    name="HR Attrition & Salaries",
                                    file_name="hr_attrition_messy.csv",
                                    rows_cols="113 records • 10 columns",
                                    description="Department attrition rate comparisons, salary correlations, and sentinel values sanitization.",
                                    icon="users",
                                ),
                                benchmark_launcher_card(
                                    name="Retail Sales & Trends",
                                    file_name="retail_sales_messy.csv",
                                    rows_cols="120 records • 8 columns",
                                    description="Payment method category distributions, monthly sales trend decomposition & return preservation.",
                                    icon="shopping-cart",
                                ),
                                benchmark_launcher_card(
                                    name="Marketing Campaigns & ROI",
                                    file_name="marketing_campaign_messy.csv",
                                    rows_cols="100 records • 8 columns",
                                    description="Multi-channel conversion rates, ad spend Pearson correlations, and volume outlier detection.",
                                    icon="trending-up",
                                ),
                                columns=rx.breakpoints(initial="1", sm="3"),
                                spacing="3",
                                width="100%",
                            ),
                            spacing="3",
                            width="100%",
                        ),

                        spacing="3",
                        width="100%",
                    ),
                    padding="2rem",
                    width="100%",
                    class_name="landing-upload-card",
                ),
                id="upload-section",
                spacing="0",
                width="100%",
                max_width="1040px",
                padding_y="3rem",
            ),

            # =========================================================
            # 3. COMPLETE FEATURE SHOWCASE (Everything in the website)
            # =========================================================
            rx.vstack(
                rx.vstack(
                    rx.text(
                        "COMPLETE CAPABILITIES",
                        font_size="0.75rem",
                        font_weight="700",
                        color=ACCENT_COLOR,
                        letter_spacing="0.1em",
                    ),
                    rx.text(
                        "Everything Built Into AutoAnalyst",
                        font_family=FONT_SERIF,
                        font_size=rx.breakpoints(initial="1.6rem", sm="2.2rem"),
                        font_weight="400",
                        color=TEXT_COLOR,
                        letter_spacing="-0.02em",
                    ),
                    rx.text(
                        "An autonomous end-to-end data intelligence platform engineered with deterministic safeguards, rigorous statistical tests, and hallucination-free reporting.",
                        font_size="0.9rem",
                        color=TEXT_MUTED,
                        text_align="center",
                        max_width="660px",
                        line_height="1.5",
                    ),
                    spacing="1",
                    align_items="center",
                    width="100%",
                    margin_bottom="2rem",
                ),

                # 6-Card Feature Grid
                rx.grid(
                    feature_card(
                        icon="sparkles",
                        title="Deterministic Data Sanitization",
                        description="Automatically detects corrupted sentinels (e.g. 999999, -1), enforces domain boundaries, preserves genuine return records, and transparently logs imputation rates with zero data leakage.",
                        badges=["Type Inference", "Sentinel Detection", "Domain Rules", "Quality Score"],
                    ),
                    feature_card(
                        icon="brain",
                        title="Automated Hypothesis Testing & EDA",
                        description="Discovers hidden anomalies without manual prompting. Computes ANOVA, two-sample t-tests, Mann-Whitney U, Pearson/Spearman correlation matrices, and time-series seasonal trend decomposition.",
                        badges=["ANOVA", "t-tests", "Correlation Matrices", "IQR Outliers"],
                    ),
                    feature_card(
                        icon="layout-dashboard",
                        title="Interactive Analytical Dashboard",
                        description="Explore publication-ready visualization charts, executive KPI summaries, segment differentials with effect size calculations, and dynamic slice filters in real time.",
                        badges=["Distribution Charts", "Executive KPIs", "Segment Differentials", "Export Charts"],
                    ),
                    feature_card(
                        icon="message-square",
                        title="Grounded Conversational AI Chat",
                        description="Engage in conversational follow-up inquiries. Every numeric claim is bound to verified dataset calculations via citation verification, strictly rejecting hallucinations or missing columns.",
                        badges=["100% Verified Claims", "Dual SQL & Heuristic", "Multi-Turn", "Safe Guardrails"],
                    ),
                    feature_card(
                        icon="activity",
                        title="Autonomous Run Monitor & Audit Trail",
                        description="Watch the autonomous agent execute in real time. Transparent step-by-step logs, token consumption meters, LLM latency benchmarks, and phase reflection traces for complete auditability.",
                        badges=["Step-by-Step Log", "Token Tracking", "Latency Audit", "Phase Reflection"],
                    ),
                    feature_card(
                        icon="file-text",
                        title="Publication-Ready Executive Reports",
                        description="Generate formal executive reports formatted for leadership and stakeholders. Includes executive business summaries, statistical tables, and downloadable styled PDF & Markdown formats.",
                        badges=["Styled PDF Export", "Markdown Export", "Methodology Disclosure", "Audit Log"],
                    ),
                    columns=rx.breakpoints(initial="1", sm="2", md="3"),
                    spacing="4",
                    width="100%",
                ),
                id="features",
                spacing="0",
                width="100%",
                padding_y="3.5rem",
            ),

            # =========================================================
            # 4. HOW IT WORKS (3-Step Autonomous Pipeline)
            # =========================================================
            rx.vstack(
                rx.vstack(
                    rx.text(
                        "THE PIPELINE",
                        font_size="0.75rem",
                        font_weight="700",
                        color=ACCENT_COLOR,
                        letter_spacing="0.1em",
                    ),
                    rx.text(
                        "How AutoAnalyst Solves Your Data",
                        font_family=FONT_SERIF,
                        font_size=rx.breakpoints(initial="1.6rem", sm="2.2rem"),
                        font_weight="400",
                        color=TEXT_COLOR,
                        letter_spacing="-0.02em",
                    ),
                    rx.text(
                        "A deterministic 3-stage intelligence loop delivering audited answers from raw inputs.",
                        font_size="0.9rem",
                        color=TEXT_MUTED,
                        text_align="center",
                        max_width="600px",
                        line_height="1.5",
                    ),
                    spacing="1",
                    align_items="center",
                    width="100%",
                    margin_bottom="2rem",
                ),

                # 3-Step Pipeline Flow Cards
                rx.grid(
                    pipeline_step(
                        step_num="1",
                        title="Ingest & Clean",
                        subtitle="Deterministic Sanitization",
                        description="Universal parsing handles CSV and tabular formats. Sentinels are flagged, invalid records isolated, and an initial dataset quality score is computed.",
                        icon="database",
                    ),
                    pipeline_step(
                        step_num="2",
                        title="Autonomous Analysis",
                        subtitle="Hypothesis Planning & Verification",
                        description="The autonomous agent plans test strategies, computes statistical differentials across segments, flags trends, and verifies all claims against computed facts.",
                        icon="cpu",
                    ),
                    pipeline_step(
                        step_num="3",
                        title="Act & Converse",
                        subtitle="Dashboards, Reports & Grounded Chat",
                        description="Interact with visual dashboards, ask natural language statistical questions with zero hallucinations, and download executive PDF reports for executive presentation.",
                        icon="file-check",
                    ),
                    columns=rx.breakpoints(initial="1", sm="3"),
                    spacing="4",
                    width="100%",
                ),
                id="how-it-works",
                spacing="0",
                width="100%",
                padding_y="3.5rem",
            ),

            # =========================================================
            # 5. TRUST & RIGOR METRICS
            # =========================================================
            rx.box(
                rx.grid(
                    rx.vstack(
                        rx.text("≥ 95%", font_family=FONT_SERIF, font_size="2.4rem", color=ACCENT_COLOR, font_weight="400"),
                        rx.text("Fact-Grounding Verification", font_size="0.825rem", font_weight="600", color=TEXT_COLOR),
                        rx.text("Every number is bound to exact statistical outputs.", font_size="0.75rem", color=TEXT_MUTED, text_align="center"),
                        spacing="1",
                        align_items="center",
                    ),
                    rx.vstack(
                        rx.text("0", font_family=FONT_SERIF, font_size="2.4rem", color=ACCENT_COLOR, font_weight="400"),
                        rx.text("Hallucinations or Leaks", font_size="0.825rem", font_weight="600", color=TEXT_COLOR),
                        rx.text("Strict numeric citation checker strips unverified claims.", font_size="0.75rem", color=TEXT_MUTED, text_align="center"),
                        spacing="1",
                        align_items="center",
                    ),
                    rx.vstack(
                        rx.text("< 3s", font_family=FONT_SERIF, font_size="2.4rem", color=ACCENT_COLOR, font_weight="400"),
                        rx.text("Statistical Execution", font_size="0.825rem", font_weight="600", color=TEXT_COLOR),
                        rx.text("High-performance DuckDB & SciPy in-memory compute.", font_size="0.75rem", color=TEXT_MUTED, text_align="center"),
                        spacing="1",
                        align_items="center",
                    ),
                    rx.vstack(
                        rx.text("100%", font_family=FONT_SERIF, font_size="2.4rem", color=ACCENT_COLOR, font_weight="400"),
                        rx.text("Deterministic Reproducibility", font_size="0.825rem", font_weight="600", color=TEXT_COLOR),
                        rx.text("Identical data yields identical audited insights every time.", font_size="0.75rem", color=TEXT_MUTED, text_align="center"),
                        spacing="1",
                        align_items="center",
                    ),
                    columns=rx.breakpoints(initial="1", sm="2", md="4"),
                    spacing="4",
                    width="100%",
                ),
                padding="2.5rem 1.5rem",
                border_radius=RADIUS_LG,
                background_color=SURFACE_COLOR,
                box_shadow=SHADOW_RAISED_SM,
                border=f"1px solid var(--border-subtle)",
                width="100%",
                margin_y="2rem",
            ),

            # =========================================================
            # 6. FINAL CALL TO ACTION (GET STARTED)
            # =========================================================
            rx.vstack(
                neu_card(
                    rx.vstack(
                        rx.text(
                            "Ready to Analyze Your Data?",
                            font_family=FONT_SERIF,
                            font_size=rx.breakpoints(initial="1.75rem", sm="2.4rem"),
                            font_weight="400",
                            color=TEXT_COLOR,
                            letter_spacing="-0.02em",
                            text_align="center",
                        ),
                        rx.text(
                            "Enter the operational workspace to upload datasets, monitor autonomous runs, explore interactive charts, chat with verified AI, and download executive PDF reports.",
                            font_size="0.95rem",
                            color=TEXT_MUTED,
                            text_align="center",
                            max_width="620px",
                            line_height="1.6",
                        ),
                        rx.link(
                            neu_button(
                                rx.hstack(
                                    rx.text("Get Started Now", font_weight="700", font_size="1rem"),
                                    rx.icon(tag="arrow-right", size=18),
                                    spacing="2",
                                    align_items="center",
                                ),
                                variant="primary",
                                padding="0.85rem 2.25rem",
                                border_radius=RADIUS_MD,
                            ),
                            href="/upload",
                            text_decoration="none",
                            margin_top="1rem",
                        ),
                        spacing="3",
                        align_items="center",
                        padding="3rem 1.5rem",
                        width="100%",
                    ),
                    width="100%",
                ),
                width="100%",
                max_width="920px",
                padding_y="3rem",
            ),

            # =========================================================
            # 7. FOOTER
            # =========================================================
            rx.hstack(
                rx.text(
                    "AutoAnalyst © 2026 • Autonomous AI Data Analyst Agent. Built for deterministic, hallucination-free data science.",
                    font_size="0.775rem",
                    color=TEXT_MUTED,
                ),
                rx.spacer(),
                rx.hstack(
                    rx.link("Datasets", href="/upload", font_size="0.775rem", color=TEXT_MUTED, text_decoration="none"),
                    rx.link("Dashboard", href="/dashboard", font_size="0.775rem", color=TEXT_MUTED, text_decoration="none"),
                    rx.link("Chat", href="/chat", font_size="0.775rem", color=TEXT_MUTED, text_decoration="none"),
                    rx.link("Reports", href="/reports", font_size="0.775rem", color=TEXT_MUTED, text_decoration="none"),
                    spacing="3",
                    align_items="center",
                ),
                width="100%",
                padding_top="2rem",
                border_top=f"1px solid var(--border-subtle)",
                align_items="center",
                wrap="wrap",
                spacing="2",
            ),

            spacing="0",
            align_items="center",
            width="100%",
        )
    )
