import plotly.graph_objects as go
import streamlit as st
import pandas as pd
from frontend.components.styles import get_theme_colors


def _get_base_layout(title: str, y_title: str = "", height: int = 330) -> dict:
    """Generate theme-aware plotly layout with high-readability defaults and zero warnings."""
    c = get_theme_colors()
    return dict(
        title=dict(
            text=f"<b>{title}</b>",
            font=dict(size=14, color=c["chart_font"]),
            x=0.01,
            y=0.96,
        ),
        height=height,
        margin=dict(l=35, r=20, t=45, b=35),
        paper_bgcolor=c["chart_paper_bg"],
        plot_bgcolor=c["chart_plot_bg"],
        font=dict(
            family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            color=c["chart_font"],
            size=11,
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=c["tooltip_bg"],
            bordercolor=c["tooltip_border"],
            font=dict(color=c["tooltip_font"], size=12),
        ),
        xaxis=dict(
            showgrid=False,
            showline=True,
            linecolor=c["chart_grid"],
            tickfont=dict(color=c["text_muted"], size=11),
            zeroline=False,
        ),
        yaxis=dict(
            title=dict(
                text=y_title,
                font=dict(color=c["text_muted"], size=11),
            ),
            gridcolor=c["chart_grid"],
            gridwidth=1,
            showline=False,
            tickfont=dict(color=c["text_muted"], size=11),
            zeroline=True,
            zerolinecolor=c["chart_zeroline"],
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color=c["text_muted"]),
        ),
    )


PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


def render_line_chart(
    x,
    y,
    title: str,
    y_title: str = "",
    color: str | None = None,
    unit: str = "",
    show_area: bool = True,
    height: int = 320,
):
    """Render a modern, ultra-readable spline line chart with area shading."""
    c = get_theme_colors()
    line_color = color or c["cyan"]

    if line_color.startswith("#"):
        hex_val = line_color.lstrip("#")
        r, g, b = tuple(int(hex_val[i : i + 2], 16) for i in (0, 2, 4))
        fill_color = f"rgba({r}, {g}, {b}, 0.12)"
    else:
        fill_color = "rgba(56, 189, 248, 0.12)"

    fig = go.Figure()

    trace_kwargs = dict(
        x=x,
        y=y,
        mode="lines+markers",
        name=y_title or title,
        line=dict(color=line_color, width=2.5, shape="spline"),
        marker=dict(
            size=6,
            color=line_color,
            line=dict(width=1.5, color="#FFFFFF" if c["is_dark"] else "#0F172A"),
        ),
        hovertemplate=f"<b>%{{y:.1f}}{unit}</b><extra></extra>",
    )

    if show_area:
        trace_kwargs["fill"] = "tozeroy"
        trace_kwargs["fillcolor"] = fill_color

    fig.add_trace(go.Scatter(**trace_kwargs))
    fig.update_layout(_get_base_layout(title, y_title=y_title, height=height))

    # Stretches full container width without heavy modebar overhead
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)


def render_multi_line_chart(
    x,
    series_dict: dict,
    title: str,
    y_title: str = "",
    unit: str = "",
    height: int = 340,
):
    """Render multiple comparison lines with distinct high-contrast colors."""
    c = get_theme_colors()
    palette = [c["cyan"], c["amber"], c["emerald"], c["purple"], c["rose"]]

    fig = go.Figure()

    for idx, (name, values) in enumerate(series_dict.items()):
        color = palette[idx % len(palette)]
        fig.add_trace(
            go.Scatter(
                x=x,
                y=values,
                mode="lines+markers",
                name=name,
                line=dict(color=color, width=2.5, shape="spline"),
                marker=dict(size=5, color=color),
                hovertemplate=f"{name}: <b>%{{y:.1f}}{unit}</b><extra></extra>",
            )
        )

    fig.update_layout(_get_base_layout(title, y_title=y_title, height=height))
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)


def render_comparison_bar_chart(
    categories: list,
    values_dict: dict,
    title: str,
    y_title: str = "",
    unit: str = "",
    height: int = 340,
):
    """Render grouped or single bar chart with direct value callouts on bars."""
    c = get_theme_colors()
    palette = [c["emerald"], c["cyan"], c["amber"], c["purple"], c["rose"]]

    fig = go.Figure()

    for idx, (label, vals) in enumerate(values_dict.items()):
        color = palette[idx % len(palette)]
        fig.add_bar(
            x=categories,
            y=vals,
            name=label,
            marker=dict(color=color, cornerradius=4),
            text=[f"{v:.1f}{unit}" for v in vals],
            textposition="outside",
            textfont=dict(size=11, color=c["chart_font"]),
            hovertemplate=f"{label}: <b>%{{y:.1f}}{unit}</b><extra></extra>",
        )

    layout = _get_base_layout(title, y_title=y_title, height=height)
    layout["barmode"] = "group"
    layout["bargap"] = 0.25
    layout["bargroupgap"] = 0.1
    fig.update_layout(layout)

    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)


def render_scatter_bubble_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    size_col: str,
    color_col: str,
    hover_name: str,
    title: str,
    x_title: str,
    y_title: str,
    height: int = 360,
):
    """Render an uncluttered 2D bubble chart for Cost vs Memory footprint (markers only, clean hover)."""
    c = get_theme_colors()
    fig = go.Figure()

    status_colors = {
        "Protected (High Cost)": c["emerald"],
        "Protected (Locked)": c["emerald"],
        "Refreshed": c["emerald"],
        "Hot": c["amber"],
        "Active": c["cyan"],
        "At Risk (Large Memory)": c["rose"],
        "Eviction Candidate": c["rose"],
        "Stale / Expiring": c["text_subtle"],
    }

    for status_val in df[color_col].unique():
        sub_df = df[df[color_col] == status_val]
        color = status_colors.get(status_val, c["cyan"])

        fig.add_trace(
            go.Scatter(
                x=sub_df[x_col],
                y=sub_df[y_col],
                mode="markers",  # Markers only: avoids overlapping text clutter
                name=status_val,
                marker=dict(
                    size=sub_df[size_col].apply(
                        lambda s: max(14, min(36, (s**0.5) * 1.1))
                    ),
                    color=color,
                    opacity=0.85,
                    line=dict(
                        width=1.5,
                        color="#FFFFFF" if c["is_dark"] else "#0F172A",
                    ),
                ),
                hovertemplate=(
                    "<b>Key:</b> %{customdata[0]}<br>"
                    f"<b>{x_title}:</b> %{{x:.1f}} KB<br>"
                    f"<b>{y_title}:</b> $%{{y:.3f}}<br>"
                    "<b>Hits:</b> %{customdata[1]:,}<br>"
                    "<b>Status:</b> %{customdata[2]}<extra></extra>"
                ),
                customdata=sub_df[[hover_name, "access_count", color_col]],
            )
        )

    layout = _get_base_layout(title, y_title=y_title, height=height)
    layout["xaxis"]["title"] = dict(
        text=x_title, font=dict(color=c["text_muted"], size=11)
    )
    layout["hovermode"] = "closest"
    fig.update_layout(layout)

    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)


def render_donut_chart(
    values: list,
    labels: list,
    title: str,
    colors: list | None = None,
    height: int = 280,
):
    """Render a clean, modern donut chart for ratios like HIT / MISS distribution."""
    c = get_theme_colors()
    chart_colors = colors or [c["emerald"], c["rose"]]

    # Guard against all zeros
    total = sum(values) if values else 0
    if total == 0:
        values = [1]
        labels = ["No traffic yet"]
        chart_colors = [c["card_border"]]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.68,
                marker=dict(
                    colors=chart_colors,
                    line=dict(
                        color="#060913" if c["is_dark"] else "#FFFFFF",
                        width=2,
                    ),
                ),
                textinfo="percent+label" if total > 0 else "label",
                textposition="inside" if total > 0 else "none",
                insidetextfont=dict(
                    size=11, color="#FFFFFF", family="Inter, sans-serif"
                ),
                hovertemplate="<b>%{label}</b><br>Count: %{value:,}<br>Ratio: %{percent}<extra></extra>"
                if total > 0
                else "No traffic recorded in current window<extra></extra>",
            )
        ]
    )
    layout = _get_base_layout(title, height=height)
    layout["showlegend"] = True
    layout["legend"] = dict(
        orientation="h",
        yanchor="bottom",
        y=-0.15,
        xanchor="center",
        x=0.5,
        font=dict(size=11, color=c["text_muted"]),
    )
    fig.update_layout(layout)
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)