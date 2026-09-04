"""Reusable semantic status badges and indicator pills for the Adaptive Cache Control Center."""

import streamlit as st
from frontend.components.styles import get_theme_colors


def get_decision_badge_html(decision: str) -> str:
    """Return inline HTML for RETAIN, EVICT, or REFRESH action badge."""
    c = get_theme_colors()
    d_upper = str(decision).upper()
    if "RETAIN" in d_upper or "LOCK" in d_upper:
        bg = "rgba(16, 185, 129, 0.15)" if c["is_dark"] else "rgba(5, 150, 105, 0.12)"
        color = c["emerald"]
        border = "rgba(16, 185, 129, 0.3)"
        label = "RETAIN"
    elif "EVICT" in d_upper or "PURGE" in d_upper:
        bg = "rgba(244, 63, 94, 0.15)" if c["is_dark"] else "rgba(220, 38, 38, 0.12)"
        color = c["rose"]
        border = "rgba(244, 63, 94, 0.3)"
        label = "EVICT"
    elif "REFRESH" in d_upper or "FETCH" in d_upper:
        bg = "rgba(56, 189, 248, 0.15)" if c["is_dark"] else "rgba(2, 132, 199, 0.12)"
        color = c["cyan"]
        border = "rgba(56, 189, 248, 0.3)"
        label = "REFRESH"
    else:
        bg = "rgba(168, 85, 247, 0.15)" if c["is_dark"] else "rgba(124, 58, 237, 0.12)"
        color = c["purple"]
        border = "rgba(168, 85, 247, 0.3)"
        label = d_upper

    return (
        f'<span style="display:inline-flex;align-items:center;padding:3px 9px;border-radius:6px;'
        f'font-size:10.5px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;'
        f'background:{bg};color:{color};border:1px solid {border};font-family:monospace;">'
        f'{label}</span>'
    )


def get_status_pill_html(text: str, status_type: str = "active") -> str:
    """Return inline HTML for semantic status tags (healthy, active, warning, critical, purple)."""
    c = get_theme_colors()
    if status_type in ("healthy", "success", "protected"):
        color = c["emerald"]
        bg = "rgba(16, 185, 129, 0.12)"
        border = "rgba(16, 185, 129, 0.28)"
    elif status_type in ("warning", "hot"):
        color = c["amber"]
        bg = "rgba(245, 158, 11, 0.12)"
        border = "rgba(245, 158, 11, 0.28)"
    elif status_type in ("danger", "critical", "risk"):
        color = c["rose"]
        bg = "rgba(244, 63, 94, 0.12)"
        border = "rgba(244, 63, 94, 0.28)"
    elif status_type in ("purple", "adaptive"):
        color = c["purple"]
        bg = "rgba(168, 85, 247, 0.12)"
        border = "rgba(168, 85, 247, 0.28)"
    else:
        color = c["cyan"]
        bg = "rgba(56, 189, 248, 0.12)"
        border = "rgba(56, 189, 248, 0.28)"

    return (
        f'<span style="display:inline-flex;align-items:center;padding:2px 8px;border-radius:5px;'
        f'font-size:10px;font-weight:700;letter-spacing:0.4px;text-transform:uppercase;'
        f'background:{bg};color:{color};border:1px solid {border};">'
        f'{text}</span>'
    )
