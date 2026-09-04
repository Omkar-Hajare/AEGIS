import streamlit as st
from frontend.components.styles import get_theme_colors


def render_decision_card(decision: dict):
    """Render an intelligent adaptive decision explanation card without markdown indentation issues."""
    c = get_theme_colors()

    action = decision.get("capacity_action", "MAINTAIN")
    if action == "SCALE_UP":
        action_label = "SCALE UP"
        action_color = c["emerald"]
        action_bg = (
            "rgba(34, 197, 94, 0.12)"
            if c["is_dark"]
            else "rgba(22, 163, 74, 0.10)"
        )
    elif action == "SCALE_DOWN":
        action_label = "SCALE DOWN"
        action_color = c["amber"]
        action_bg = (
            "rgba(245, 158, 11, 0.12)"
            if c["is_dark"]
            else "rgba(217, 119, 6, 0.10)"
        )
    else:
        action_label = "STEADY STATE"
        action_color = c["text"]
        action_bg = (
            "rgba(255, 255, 255, 0.08)"
            if c["is_dark"]
            else "rgba(0, 0, 0, 0.05)"
        )

    reason = decision.get("reason", "Workload stable within thresholds.")
    rec_cap = decision.get(
        "recommended_capacity_mb",
        int(decision.get("recommended_capacity_bytes", 536870912) / (1024 * 1024)),
    )
    current_cap = decision.get("current_capacity_mb", 384)
    marginal_gain = decision.get("marginal_utility_pct", 28.4)
    cycle_id = decision.get("eval_cycle_id", "EV-9942")

    eviction_keys = decision.get("eviction_keys", [])
    eviction_color = c["rose"]
    eviction_tags = "".join(
        [
            f'<span style="background:rgba(239,68,68,0.10);color:{eviction_color};border:1px solid rgba(239,68,68,0.22);border-radius:4px;padding:2px 7px;font-size:11px;margin-right:6px;font-family:monospace;font-weight:600;">{k}</span>'
            for k in eviction_keys
        ]
    )

    retained_keys = decision.get("retained_high_value_keys", [])
    retained_color = c["emerald"]
    retained_tags = "".join(
        [
            f'<span style="background:rgba(34,197,94,0.10);color:{retained_color};border:1px solid rgba(34,197,94,0.22);border-radius:4px;padding:2px 7px;font-size:11px;margin-right:6px;font-family:monospace;font-weight:600;">{k}</span>'
            for k in retained_keys
        ]
    )

    evict_content = (
        eviction_tags
        if eviction_tags
        else f'<span style="color:{c["text_muted"]};font-size:11px;">None scheduled</span>'
    )
    retain_content = (
        retained_tags
        if retained_tags
        else f'<span style="color:{c["text_muted"]};font-size:11px;">Default retention active</span>'
    )
    grid_bg = "rgba(255, 255, 255, 0.03)" if c["is_dark"] else "rgba(0, 0, 0, 0.03)"

    html = (
        f'<div class="hero-card decision-card" style="padding:20px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid {c["card_border"]};padding-bottom:12px;margin-bottom:14px;">'
        f'<div>'
        f'<span style="font-size:11px;font-weight:700;color:{c["text_muted"]};text-transform:uppercase;letter-spacing:0.6px;">ARBITER CYCLE #{cycle_id}</span>'
        f'<div style="margin-top:5px;">'
        f'<span style="font-size:13px;font-weight:700;color:{action_color};background:{action_bg};border:1px solid {c["card_border"]};padding:3px 10px;border-radius:6px;letter-spacing:0.5px;">{action_label}</span>'
        f'</div>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<div style="font-size:11px;color:{c["text_muted"]};font-weight:600;text-transform:uppercase;">Marginal Gain</div>'
        f'<div style="font-size:17px;font-weight:800;color:{c["emerald"]};">+{marginal_gain}% ROI</div>'
        f'</div>'
        f'</div>'
        f'<p style="font-size:13px;color:{c["text"]};margin:0 0 14px 0;line-height:1.55;">{reason}</p>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;background:{grid_bg};border:1px solid {c["card_border"]};border-radius:8px;padding:12px;margin-bottom:14px;">'
        f'<div>'
        f'<div style="font-size:10.5px;color:{c["text_muted"]};font-weight:700;text-transform:uppercase;">Current Allocation</div>'
        f'<div style="font-size:16px;font-weight:800;color:{c["text"]};margin-top:2px;">{current_cap} MB</div>'
        f'</div>'
        f'<div>'
        f'<div style="font-size:10.5px;color:{c["text_muted"]};font-weight:700;text-transform:uppercase;">Target Capacity</div>'
        f'<div style="font-size:16px;font-weight:800;color:{action_color};margin-top:2px;">{rec_cap} MB</div>'
        f'</div>'
        f'</div>'
        f'<div style="margin-top:10px;">'
        f'<div style="font-size:11px;font-weight:700;color:{c["text_muted"]};margin-bottom:5px;text-transform:uppercase;letter-spacing:0.5px;">Scheduled Evictions (Low Cost/MB Density):</div>'
        f'<div>{evict_content}</div>'
        f'</div>'
        f'<div style="margin-top:12px;">'
        f'<div style="font-size:11px;font-weight:700;color:{c["text_muted"]};margin-bottom:5px;text-transform:uppercase;letter-spacing:0.5px;">Protected High-Cost Keys:</div>'
        f'<div>{retain_content}</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)
