"""System State & Observation Window Control View.

Consumes FastAPI /telemetry/system and /telemetry/window/reset.
Surfaces honest cache usage, unconstrained capacity state, zero evictions,
and deliberate confirmation for observation window rotation.
"""

import streamlit as st
from frontend.services.telemetry_service import get_system_state, reset_telemetry_window
from frontend.components.styles import get_theme_colors
from frontend.components.metric_card import render_metric_card
from frontend.utils.formatting import (
    format_bytes,
    format_int,
    format_duration,
    format_timestamp,
)


def render_system_view():
    """Render System State and Window Reset Control Center."""
    c = get_theme_colors()
    sys_state = get_system_state()

    # Header Title Block with cleanly aligned right badge
    header_html = (
        f'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin: 8px 0 22px 0; flex-wrap: wrap; gap: 12px;">'
        f'<div>'
        f'<h1 style="margin: 0 0 6px 0; font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; color: {c["text"]} !important;">'
        f'System State & <span style="color: {c["cyan"]} !important;">Runtime Topology</span>'
        f'</h1>'
        f'<p style="margin: 0; font-size: 13.5px; line-height: 1.5; color: {c["text_muted"]}; max-width: 840px;">'
        f'Runtime cache usage, active in-memory object tracking, logical capacity constraints, and observation window lifecycle management.'
        f'</p>'
        f'</div>'
        f'<div style="display: flex; align-items: center; padding-top: 6px;">'
        f'<span style="font-size: 10.5px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; background: rgba(56, 189, 248, 0.12); color: {c["cyan"]}; border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 6px; padding: 4px 12px; white-space: nowrap;">'
        f'GET /TELEMETRY/SYSTEM'
        f'</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # HERO SYSTEM METRICS STRIP
    # --------------------------------------------------
    s1, s2, s3, s4 = st.columns(4)

    usage_bytes = sys_state.get("cache_usage_bytes", 0)
    capacity_bytes = sys_state.get("cache_capacity_bytes")
    object_count = sys_state.get("object_count", 0)
    backend_calls = sys_state.get("backend_calls", 0)
    evictions = sys_state.get("cache_evictions", 0)

    with s1:
        render_metric_card(
            title="Cache Memory Usage",
            value=format_bytes(usage_bytes),
            subtitle=f"{format_int(usage_bytes)} total bytes tracked",
            tag="MEMORY",
            delta="In-Memory Cache Layer",
            delta_color=c["cyan"],
            tooltip="Sum of payload sizes of currently tracked cache entries in RAM.",
        )

    with s2:
        cap_display = format_bytes(capacity_bytes)
        render_metric_card(
            title="Capacity Constraint",
            value=cap_display if capacity_bytes else "Unconstrained",
            subtitle="Configured logical ceiling",
            tag="BOUNDS",
            delta="Not restricted by ceiling" if not capacity_bytes else "Quota enforced",
            delta_color=c["emerald"] if not capacity_bytes else c["amber"],
            tooltip="Logical maximum memory footprint. Reports 'Unconstrained / not configured' when unconstrained in backend.",
        )

    with s3:
        render_metric_card(
            title="Active Cache Keys",
            value=f"{format_int(object_count)} Objects",
            subtitle=f"Backend calls: {format_int(backend_calls)}",
            tag="REGISTRY",
            delta="Tracked by Manager",
            delta_color=c["emerald"],
            tooltip="Total unique key-value objects presently registered and managed in cache memory.",
        )

    with s4:
        render_metric_card(
            title="Eviction Pruning Count",
            value=f"{format_int(evictions)} Evictions",
            subtitle="Current window observations",
            tag="PRUNING",
            delta="Nominal (Zero Evictions)",
            delta_color="#10B981",
            tooltip="Number of objects evicted from cache in current window. Currently 0 because eviction is unconstrained.",
        )

    st.write("")

    # --------------------------------------------------
    # RUNTIME ARCHITECTURE & BOUNDARY EXPLANATION
    # --------------------------------------------------
    col_arch, col_reset = st.columns([1.3, 1.2])

    with col_arch:
        st.markdown(
            f'<h3 style="font-size: 1.15rem; font-weight: 700; color: {c["text"]}; margin-bottom: 12px;">'
            f'Cache Subsystem Status'
            f'</h3>',
            unsafe_allow_html=True,
        )

        subsystem_html = (
            f'<div class="hero-card" style="padding: 16px 18px; margin-bottom: 14px; border-radius: 10px; background: {c["card_bg"]}; border: 1px solid {c["card_border"]};">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">'
            f'<span style="font-size: 13.5px; font-weight: 700; color: {c["text"]};">Backend Cache Abstraction</span>'
            f'<span class="badge-pill badge-protected">ONLINE</span>'
            f'</div>'
            f'<p style="font-size: 12px; color: {c["text_muted"]}; margin: 0 0 10px 0; line-height: 1.45;">'
            f'Managed by FastAPI <code>create_cache_manager()</code>. Employs in-memory or Redis key-value storage with automatic metadata tracking.'
            f'</p>'
            f'<div style="display: flex; gap: 8px;">'
            f'<span style="font-size: 10.5px; font-weight: 700; color: {c["cyan"]}; background: rgba(56, 189, 248, 0.12); padding: 2px 7px; border-radius: 4px;">Memory: {format_bytes(usage_bytes)}</span>'
            f'<span style="font-size: 10.5px; font-weight: 700; color: #10B981; background: rgba(16, 185, 129, 0.12); padding: 2px 7px; border-radius: 4px;">Objects: {format_int(object_count)}</span>'
            f'</div>'
            f'</div>'
            f'<div class="hero-card" style="padding: 16px 18px; border-radius: 10px; background: {c["card_bg"]}; border: 1px solid {c["card_border"]};">'
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">'
            f'<span style="font-size: 13.5px; font-weight: 700; color: {c["text"]};">Telemetry State Collector</span>'
            f'<span class="badge-pill badge-active">WINDOW ACTIVE</span>'
            f'</div>'
            f'<p style="font-size: 12px; color: {c["text_muted"]}; margin: 0; line-height: 1.45;">'
            f'Active Window Elapsed: <b>{format_duration(sys_state.get("window_seconds"))}</b> &bull; Snapshot: <code>{format_timestamp(sys_state.get("timestamp"))}</code>'
            f'</p>'
            f'</div>'
        )
        st.markdown(subsystem_html, unsafe_allow_html=True)

    with col_reset:
        st.markdown(
            f'<h3 style="font-size: 1.15rem; font-weight: 700; color: {c["text"]}; margin-bottom: 12px;">'
            f'Telemetry Window Lifecycle'
            f'</h3>',
            unsafe_allow_html=True,
        )

        reset_card_html = (
            f'<div class="decision-card" style="padding: 16px; margin-bottom: 14px; border-radius: 10px; background: {c["card_bg"]}; border: 1px solid {c["card_border"]};">'
            f'<span style="font-size: 11px; font-weight: 700; color: {c["amber"]}; text-transform: uppercase; letter-spacing: 0.5px;">STATE-CHANGING ACTION:</span>'
            f'<p style="font-size: 12px; color: {c["text"]}; margin: 8px 0 12px 0; line-height: 1.45;">'
            f'Triggering a window reset rotates the active observation window into the previous history window and resets rate/call counters.<br>'
            f'<b>Important:</b> This resets window telemetry only; it <u>does not delete</u> cached objects or in-memory data.'
            f'</p>'
            f'</div>'
        )
        st.markdown(reset_card_html, unsafe_allow_html=True)

        with st.expander("⚠️ Confirm Telemetry Window Rotation", expanded=False):
            st.warning("Are you sure you want to rotate the telemetry window? Window rates will restart from 0s.")
            if st.button("Confirm: Reset Telemetry Window", key="btn_confirm_reset_window", type="primary", width="stretch"):
                res = reset_telemetry_window()
                st.toast("⚡ Telemetry window rotated: Window counters reset!", icon="🔄")
                st.rerun()
