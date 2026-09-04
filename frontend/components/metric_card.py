import streamlit as st
from frontend.components.styles import get_theme_colors


def render_metric_card(
    title: str,
    value: str,
    subtitle: str = "",
    tag: str = "",
    delta: str = "",
    delta_color: str = "#22C55E",
    tooltip: str = "",
    progress_pct: float | None = None,
    progress_value: float | None = None,
    progress_color: str | None = None,
    is_floating: bool = False,
):
    """Render a premium technical metric card with baseline delta and explanatory tooltip."""
    c = get_theme_colors()

    # Normalize progress_pct vs progress_value (accepts 0.0-1.0 or 0-100)
    effective_progress = progress_pct if progress_pct is not None else progress_value
    if effective_progress is not None:
        if 0.0 <= effective_progress <= 1.0:
            effective_progress = effective_progress * 100.0

    # Adapt delta color in light mode for maximum legibility
    actual_delta_color = delta_color
    if not c["is_dark"]:
        if delta_color in ("#F59E0B", "amber"):
            actual_delta_color = "#D97706"
        elif delta_color in ("#EF4444", "#F43F5E", "red", "rose"):
            actual_delta_color = "#DC2626"
        elif delta_color in ("#22C55E", "#10B981", "green", "emerald"):
            actual_delta_color = "#16A34A"
        elif delta_color in ("#A78BFA", "#A855F7", "purple"):
            actual_delta_color = "#7C3AED"
        elif delta_color in ("#60A5FA", "#38BDF8", "cyan", "blue"):
            actual_delta_color = "#2563EB"

    delta_html = (
        f'<div style="font-size:11.5px;font-weight:600;color:{actual_delta_color};margin-top:4px;display:flex;align-items:center;gap:4px;">'
        f'{delta}</div>'
        if delta
        else ""
    )

    tag_html = (
        f'<span style="font-size:9.5px;font-weight:700;background:{"rgba(255,255,255,0.06)" if c["is_dark"] else "rgba(0,0,0,0.04)"};color:{c["text_muted"]};border:1px solid {c["card_border"]};border-radius:4px;padding:2px 6px;letter-spacing:0.5px;text-transform:uppercase;">{tag}</span>'
        if tag
        else ""
    )

    tooltip_html = (
        f'<span title="{tooltip}" style="cursor:help;font-size:11px;color:{c["text_subtle"]};margin-left:4px;">ⓘ</span>'
        if tooltip
        else ""
    )

    bar_html = ""
    if effective_progress is not None:
        p_pct = min(100.0, max(0.0, float(effective_progress)))
        p_col = progress_color or c["emerald"]
        bar_bg = "rgba(255, 255, 255, 0.08)" if c["is_dark"] else "rgba(0, 0, 0, 0.08)"
        bar_html = (
            f'<div style="background:{bar_bg};height:4px;border-radius:2px;overflow:hidden;margin-top:8px;">'
            f'<div style="background:{p_col};width:{p_pct}%;height:100%;border-radius:2px;"></div>'
            f'</div>'
        )

    html = (
        f'<div class="hero-card metric-card" style="padding:16px 18px;min-height:130px;height:100%;display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div style="display:flex;align-items:center;">'
        f'<span style="color:{c["text_muted"]};font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;">{title}</span>'
        f'{tooltip_html}'
        f'</div>'
        f'{tag_html}'
        f'</div>'
        f'<div>'
        f'<div style="font-size:26px;font-weight:800;color:{c["text"]};margin-top:6px;letter-spacing:-0.6px;line-height:1.1;">{value}</div>'
        f'{delta_html}'
        f'{bar_html}'
        f'<div style="color:{c["text_muted"]};font-size:11px;margin-top:4px;font-weight:500;">{subtitle}</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)