import streamlit as st
from frontend.components.styles import get_theme_colors


def render_metric_card(
    title: str,
    value: str,
    subtitle: str = "",
    tag: str = "",
    delta: str = "",
    delta_color: str = "#10B981",
    is_floating: bool = False,
):
    """Render a modern technical metric card with high contrast in both themes."""
    c = get_theme_colors()

    # Adapt delta color in light mode for maximum legibility
    actual_delta_color = delta_color
    if not c["is_dark"]:
        if delta_color in ("#F59E0B", "amber"):
            actual_delta_color = "#B45309"
        elif delta_color in ("#F43F5E", "#rose", "red"):
            actual_delta_color = "#DC2626"
        elif delta_color in ("#38BDF8", "cyan"):
            actual_delta_color = "#0284C7"
        elif delta_color in ("#A855F7", "purple"):
            actual_delta_color = "#7C3AED"

    delta_html = (
        f'<div style="font-size:11.5px;font-weight:600;color:{actual_delta_color};margin-top:4px;">{delta}</div>'
        if delta
        else ""
    )
    tag_html = (
        f'<span style="font-size:10px;font-weight:700;background:rgba(56,189,248,0.12);color:{c["cyan"]};border:1px solid rgba(56,189,248,0.25);border-radius:4px;padding:2px 6px;letter-spacing:0.5px;">{tag}</span>'
        if tag
        else ""
    )
    floating_cls = "floating-element" if is_floating else ""

    html = (
        f'<div class="hero-card {floating_cls}" style="padding:16px 18px;min-height:125px;display:flex;flex-direction:column;justify-content:space-between;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="color:{c["text_muted"]};font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;">{title}</span>'
        f'{tag_html}'
        f'</div>'
        f'<div>'
        f'<div style="font-size:26px;font-weight:800;color:{c["text"]};margin-top:6px;letter-spacing:-0.5px;">{value}</div>'
        f'{delta_html}'
        f'<div style="color:{c["text_subtle"]};font-size:11.5px;margin-top:3px;font-weight:500;">{subtitle}</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)