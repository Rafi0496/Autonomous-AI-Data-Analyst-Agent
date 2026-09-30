"""Headless Chart Rendering Engine via Matplotlib (Agg backend).

Renders standardized chart_spec dictionaries to production-grade PNG images
for PDF and Word exports with consistent palettes, readable typography,
and crisp layout formatting.
"""
from __future__ import annotations
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Premium curated palette
PALETTE = {
    "primary": "#4f46e5",    # Indigo
    "secondary": "#06b6d4",  # Cyan
    "accent": "#10b981",     # Emerald
    "warning": "#f59e0b",    # Amber
    "danger": "#ef4444",     # Rose
    "neutral_dark": "#1e293b", # Slate-800
    "neutral_light": "#f8fafc",# Slate-50
    "grid": "#e2e8f0",       # Slate-200
    "text": "#334155",       # Slate-700
    "subtext": "#64748b"     # Slate-500
}

PALETTE_SERIES = [
    "#4f46e5", "#06b6d4", "#10b981", "#f59e0b",
    "#8b5cf6", "#ec4899", "#3b82f6", "#14b8a6"
]


def apply_theme(ax: plt.Axes, title: str, x_label: str, y_label: str):
    """Apply consistent styling across all chart types."""
    ax.set_title(title, fontsize=12, fontweight="bold", color=PALETTE["neutral_dark"], pad=14)
    if x_label:
        ax.set_xlabel(x_label, fontsize=10, fontweight="semibold", color=PALETTE["text"], labelpad=8)
    if y_label:
        ax.set_ylabel(y_label, fontsize=10, fontweight="semibold", color=PALETTE["text"], labelpad=8)

    ax.tick_params(colors=PALETTE["subtext"], labelsize=9)
    ax.grid(True, linestyle="--", linewidth=0.7, alpha=0.6, color=PALETTE["grid"])
    ax.set_axisbelow(True)

    # Clean spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(PALETTE["grid"])
    ax.spines["bottom"].set_color(PALETTE["grid"])


def render_chart_to_png(
    chart_spec: Dict[str, Any],
    output_path: Optional[Union[str, Path]] = None,
    width_in: float = 7.0,
    height_in: float = 4.0,
    dpi: int = 150
) -> bytes:
    """
    Render a declarative chart specification into PNG bytes.
    Optionally saves to output_path if provided.
    """
    chart_type = chart_spec.get("chart_type", "bar").lower()
    title = chart_spec.get("title", "Insight Visualization")
    x_label = chart_spec.get("x_label", "")
    y_label = chart_spec.get("y_label", "")
    data = chart_spec.get("data") or []
    orientation = chart_spec.get("orientation", "vertical")

    fig, ax = plt.subplots(figsize=(width_in, height_in), dpi=dpi)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    try:
        # 1. BAR CHART (vertical or horizontal, with error bars where available)
        if chart_type == "bar":
            if orientation == "horizontal":
                # Horizontal bar (e.g. data quality imputation rates)
                labels = [str(item.get("label", item.get("column", f"Item {i}"))) for i, item in enumerate(data)]
                values = [float(item.get("value", item.get("rate", 0.0))) for item in data]
                
                y_pos = np.arange(len(labels))
                bars = ax.barh(y_pos, values, color=PALETTE["primary"], edgecolor="none", height=0.6, alpha=0.88)
                ax.set_yticks(y_pos)
                ax.set_yticklabels(labels)
                ax.invert_yaxis()  # top-down ranking
                
                # Annotate value on bar
                for bar in bars:
                    w = bar.get_width()
                    ax.text(w + (max(values, default=1.0) * 0.015), bar.get_y() + bar.get_height() / 2,
                            f"{w:.1f}%" if "rate" in x_label.lower() or "%" in title else f"{w:.1f}",
                            va="center", ha="left", fontsize=8.5, color=PALETTE["text"], fontweight="semibold")
            else:
                # Vertical bar (e.g. segment comparison)
                labels = [str(item.get("label", item.get("category", item.get("segment", f"Item {i}")))) for i, item in enumerate(data)]
                values = [float(item.get("value", item.get("mean", item.get("median", 0.0)))) for item in data]
                errors = [float(item.get("error", 0.0)) for item in data]
                has_errors = any(e > 0 for e in errors)
                yerr = errors if has_errors else None

                x_pos = np.arange(len(labels))
                colors = [PALETTE_SERIES[i % len(PALETTE_SERIES)] for i in range(len(labels))]
                bars = ax.bar(x_pos, values, yerr=yerr, capsize=4, color=colors, edgecolor="none", width=0.55, alpha=0.9)
                ax.set_xticks(x_pos)
                ax.set_xticklabels(labels, rotation=15 if any(len(l) > 7 for l in labels) else 0, ha="right" if any(len(l) > 7 for l in labels) else "center")

        # 2. LINE CHART (e.g. trend analysis)
        elif chart_type == "line":
            if isinstance(data, list) and data:
                x_vals = [str(item.get("x", item.get("date", str(i)))) for i, item in enumerate(data)]
                y_vals = [float(item.get("y", item.get("value", 0.0))) for item in data]
                
                x_idx = np.arange(len(x_vals))
                ax.plot(x_idx, y_vals, color=PALETTE["primary"], linewidth=2.2, marker="o", markersize=4.5, label="Observed")

                # Rolling average if present
                rolling_vals = [item.get("rolling") for item in data if item.get("rolling") is not None]
                if len(rolling_vals) == len(data):
                    ax.plot(x_idx, rolling_vals, color=PALETTE["warning"], linewidth=1.8, linestyle="--", label="Rolling Average")
                    ax.legend(frameon=False, fontsize=8.5, loc="best")

                # Thin out x ticks if many
                if len(x_vals) > 10:
                    step = max(1, len(x_vals) // 7)
                    ax.set_xticks(x_idx[::step])
                    ax.set_xticklabels(x_vals[::step], rotation=25, ha="right")
                else:
                    ax.set_xticks(x_idx)
                    ax.set_xticklabels(x_vals, rotation=25 if len(x_vals) > 4 else 0, ha="right" if len(x_vals) > 4 else "center")

        # 3. SCATTER CHART (e.g. pairwise correlation)
        elif chart_type == "scatter":
            if isinstance(data, list) and data:
                x_pts = [float(item.get("x", 0.0)) for item in data]
                y_pts = [float(item.get("y", 0.0)) for item in data]
                ax.scatter(x_pts, y_pts, color=PALETTE["primary"], alpha=0.7, edgecolors="none", s=36)
                
                # Fit trendline if >= 2 points
                if len(x_pts) >= 2 and np.std(x_pts) > 1e-6:
                    z = np.polyfit(x_pts, y_pts, 1)
                    p = np.poly1d(z)
                    x_line = np.linspace(min(x_pts), max(x_pts), 100)
                    ax.plot(x_line, p(x_line), color=PALETTE["danger"], linestyle="--", linewidth=1.5, label="Trendline")
                    ax.legend(frameon=False, fontsize=8.5)

        # 4. HEATMAP (e.g. 3+ column correlation)
        elif chart_type == "heatmap":
            if isinstance(data, dict):
                cols = data.get("columns", [])
                matrix = data.get("matrix", [])
                if matrix and cols:
                    arr = np.array(matrix, dtype=float)
                    cax = ax.imshow(arr, cmap="coolwarm", vmin=-1.0, vmax=1.0)
                    fig.colorbar(cax, ax=ax, fraction=0.046, pad=0.04)

                    ax.set_xticks(np.arange(len(cols)))
                    ax.set_yticks(np.arange(len(cols)))
                    ax.set_xticklabels(cols, rotation=35, ha="right", fontsize=8.5)
                    ax.set_yticklabels(cols, fontsize=8.5)

                    # Annotate cell values
                    for i in range(len(cols)):
                        for j in range(len(cols)):
                            val = arr[i, j]
                            text_col = "white" if abs(val) > 0.55 else "black"
                            ax.text(j, i, f"{val:.2f}", ha="center", va="center", color=text_col, fontsize=8, fontweight="semibold")

        # 5. BOX CHART (e.g. outlier / distribution)
        elif chart_type == "box":
            box_data = []
            labels = []
            if isinstance(data, list):
                for item in data:
                    if "values" in item:
                        box_data.append(item["values"])
                        labels.append(str(item.get("label", item.get("category", "Group"))))
                    elif "q1" in item:
                        # Reconstruct pseudo distribution for box rendering
                        q1 = float(item["q1"])
                        med = float(item["median"])
                        q3 = float(item["q3"])
                        iqr = max(1e-4, q3 - q1)
                        sample = [q1 - 1.2 * iqr, q1, med, q3, q3 + 1.2 * iqr]
                        box_data.append(sample)
                        labels.append(str(item.get("label", item.get("column", "Distribution"))))
            elif isinstance(data, dict) and "values" in data:
                box_data.append(data["values"])
                labels.append(data.get("label", "Distribution"))

            if box_data:
                try:
                    bp = ax.boxplot(box_data, patch_artist=True, tick_labels=labels, widths=0.5)
                except TypeError:
                    bp = ax.boxplot(box_data, patch_artist=True, labels=labels, widths=0.5)
                for box in bp["boxes"]:
                    box.set_facecolor(PALETTE["primary"])
                    box.set_alpha(0.65)
                for median in bp["medians"]:
                    median.set(color=PALETTE["danger"], linewidth=2)

        # 6. HISTOGRAM (e.g. outlier frequency)
        elif chart_type == "histogram":
            if isinstance(data, list) and data:
                if "bin" in data[0]:
                    bins = [str(item["bin"]) for item in data]
                    counts = [float(item.get("count", 0)) for item in data]
                    x_pos = np.arange(len(bins))
                    ax.bar(x_pos, counts, color=PALETTE["secondary"], edgecolor="none", width=0.8, alpha=0.85)
                    ax.set_xticks(x_pos)
                    ax.set_xticklabels(bins, rotation=20, ha="right", fontsize=8.5)
                elif "values" in data[0]:
                    vals = data[0]["values"]
                    ax.hist(vals, bins=15, color=PALETTE["secondary"], edgecolor="white", alpha=0.85)

        apply_theme(ax, title, x_label, y_label)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
        buf.seek(0)
        png_bytes = buf.getvalue()

        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(png_bytes)

        return png_bytes
    finally:
        plt.close(fig)
