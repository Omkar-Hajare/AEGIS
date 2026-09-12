"""Reusable semantic status badges and indicator pills for AEGIS — Adaptive Cache Control Center."""

import streamlit as st
from frontend.components.styles import get_theme_colors


def get_decision_badge_html(decision: str) -> str:
    """Return inline HTML for RETAIN, EVICT, or REFRESH action badge."""
    c = get_theme_colors()
    d_upper = str(decision).upper()
    if "RETAIN" in d_upper or "LOCK" in d_upper:
        bg = "rgba(34, 197, 94, 0.10)" if c["is_dark"] else "rgba(22, 163, 74, 0.08)"
        color = c["emerald"]
        border = "rgba(34, 197, 94, 0.22)"
        label = "RETAIN"
    elif "EVICT" in d_upper or "PURGE" in d_upper:
        bg = "rgba(239, 68, 68, 0.10)" if c["is_dark"] else "rgba(220, 38, 38, 0.08)"
        color = c["rose"]
        border = "rgba(239, 68, 68, 0.22)"
        label = "EVICT"
    elif "REFRESH" in d_upper or "FETCH" in d_upper:
        bg = "rgba(245, 158, 11, 0.10)" if c["is_dark"] else "rgba(217, 119, 6, 0.08)"
        color = c["amber"]
        border = "rgba(245, 158, 11, 0.22)"
        label = "REFRESH"
    else:
        bg = "rgba(167, 139, 250, 0.10)" if c["is_dark"] else "rgba(124, 58, 237, 0.08)"
        color = c["purple"]
        border = "rgba(167, 139, 250, 0.22)"
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
    dark = c["is_dark"]
    if status_type in ("healthy", "success", "protected"):
        color = c["emerald"]
        bg = "rgba(34, 197, 94, 0.10)"
        border = "rgba(34, 197, 94, 0.22)"
    elif status_type in ("warning", "hot", "refresh"):
        color = c["amber"]
        bg = "rgba(245, 158, 11, 0.10)"
        border = "rgba(245, 158, 11, 0.22)"
    elif status_type in ("danger", "critical", "risk", "evict"):
        color = c["rose"]
        bg = "rgba(239, 68, 68, 0.10)"
        border = "rgba(239, 68, 68, 0.22)"
    elif status_type in ("purple", "adaptive"):
        color = c["purple"]
        bg = "rgba(167, 139, 250, 0.10)"
        border = "rgba(167, 139, 250, 0.22)"
    elif status_type in ("blue", "info"):
        color = c["blue"]
        bg = "rgba(96, 165, 250, 0.10)"
        border = "rgba(96, 165, 250, 0.22)"
    else:
        color = c["text_muted"]
        bg = "rgba(255, 255, 255, 0.05)" if dark else "rgba(0, 0, 0, 0.04)"
        border = c["card_border"]

    return (
        f'<span style="display:inline-flex;align-items:center;padding:2px 8px;border-radius:5px;'
        f'font-size:10px;font-weight:700;letter-spacing:0.4px;text-transform:uppercase;'
        f'background:{bg};color:{color};border:1px solid {border};">'
        f'{text}</span>'
    )
