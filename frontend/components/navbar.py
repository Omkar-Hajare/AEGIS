import streamlit as st
from frontend.components.styles import (
    get_theme_colors,
    get_backend_status,
    is_dark_mode,
)

# Clean, modern, concise navigation labels
NAV_OPTIONS = [
    "Overview",
    "Cache Objects",
    "Decisions",
    "Workload",
    "Benchmarks",
]


def render_top_navbar(current_tab: str = "Overview") -> str:
    """Render high-performance, sticky top navigation bar with branding, clean segmented tabs, and quick theme toggle."""
    c = get_theme_colors()
    b_status = get_backend_status()
    is_live = b_status["is_live"]
    status_dot_color = "#10B981" if is_live else c["amber"]
    status_label = "REDIS TIER-1" if is_live else "DEMO TRACE"

    if "active_nav" not in st.session_state:
        st.session_state["active_nav"] = current_tab

    col_brand, col_nav, col_actions = st.columns(
        [1.15, 2.85, 0.95], vertical_alignment="center"
    )

    with col_brand:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 10px; padding: 2px 0;">
                <div style="display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 8px; background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.35);">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{c["cyan"]}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                </div>
                <div>
                    <div style="display: flex; align-items: center; gap: 7px;">
                        <span style="font-weight: 800; font-size: 15px; letter-spacing: -0.3px; color: {c["text"]};">
                            AdaptiveCache
                        </span>
                        <span style="font-size: 9.5px; font-weight: 700; color: {status_dot_color}; background: {'rgba(255,255,255,0.06)' if c['is_dark'] else 'rgba(0,0,0,0.04)'}; border: 1px solid {c["card_border"]}; padding: 1px 6px; border-radius: 4px; letter-spacing: 0.5px;">
                            {status_label}
                        </span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_nav:
        # Default to session state
        active_val = st.session_state.get("active_nav", current_tab)
        # Handle legacy labels mapping
        label_map = {
            "Executive Overview": "Overview",
            "Adaptive Decisions": "Decisions",
            "Workload Simulator": "Workload",
            "Policy Benchmarks": "Benchmarks",
        }
        active_val = label_map.get(active_val, active_val)
        if active_val not in NAV_OPTIONS:
            active_val = NAV_OPTIONS[0]
            st.session_state["active_nav"] = active_val

        selected = st.segmented_control(
            "Navigation Menu",
            options=NAV_OPTIONS,
            default=active_val,
            label_visibility="collapsed",
            key="top_navbar_segmented_control",
        )

        if selected and selected != active_val:
            st.session_state["active_nav"] = selected
            st.rerun()

    with col_actions:
        is_dark = is_dark_mode()
        btn_label = "☀️ Light" if is_dark else "🌙 Dark"
        btn_help = "Toggle between Cyber Obsidian Dark and Clean Light mode"

        theme_col, refresh_col = st.columns([1.1, 1.0], vertical_alignment="center")
        with theme_col:
            if st.button(
                btn_label, key="navbar_theme_toggle_btn", help=btn_help, width="stretch"
            ):
                st.session_state["dark_mode"] = not is_dark
                st.rerun()
        with refresh_col:
            if st.button(
                "⚡ Sync", key="navbar_sync_btn", help="Re-sync cache telemetry", width="stretch"
            ):
                st.cache_data.clear()
                st.rerun()

    return st.session_state.get("active_nav", current_tab)
