"""Cache Performance View.

Provides in-depth observability into cache hit/miss behavior, backend calls vs total
requests, read latency improvement, and key access distribution using real telemetry.
"""

import streamlit as st
import pandas as pd
from frontend.services.telemetry_service import get_telemetry_observation
from frontend.components.styles import get_theme_colors
from frontend.components.metric_card import render_metric_card
from frontend.components.charts import render_donut_chart, render_comparison_bar_chart
from frontend.utils.formatting import (
    format_percentage,
    format_latency,
    format_int,
    format_duration,
    format_timestamp,
)


def render_cache_performance_view():
    """Render dedicated Cache Performance and Telemetry Observability page."""
    c = get_theme_colors()
    obs = get_telemetry_observation()

    # Header Title Block with cleanly aligned right badge
    header_html = (
        f'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin: 0 0 12px 0; flex-wrap: wrap; gap: 12px;">'
        f'<div>'
        f'<h1 style="margin: 0 0 6px 0; font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; color: {c["text"]} !important;">'
        f'Cache Performance & <span style="color: {c["text_muted"]} !important; font-weight: 600;">Hit/Miss Telemetry</span>'
        f'</h1>'
        f'<p style="margin: 0; font-size: 13.5px; line-height: 1.5; color: {c["text_muted"]}; max-width: 840px;">'
        f'Live observation of cache hit/miss ratios, read latency preservation, and backend call attenuation across time-windowed traffic.'
        f'</p>'
        f'</div>'
        f'<div style="display: flex; align-items: center; padding-top: 6px;">'
        f'<span style="font-size: 10.5px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; background: {"rgba(255, 255, 255, 0.06)" if c["is_dark"] else "rgba(0, 0, 0, 0.04)"}; color: {c["text_muted"]}; border: 1px solid {c["card_border"]}; border-radius: 6px; padding: 4px 12px; white-space: nowrap;">'
        f'OBSERVATION WINDOW &bull; {format_duration(obs.get("window_seconds"))}'
        f'</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # HERO KPI STRIP
    # --------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)

    total_reqs = obs.get("total_requests", 0)
    hits = obs.get("cache_hits", 0)
    misses = obs.get("cache_misses", 0)
    backend_calls = obs.get("backend_calls", 0)
    hit_rate = obs.get("hit_rate", 0.0)
    miss_rate = obs.get("miss_rate", 0.0)
    latency_ms = obs.get("backend_latency_ms", 0.0)
    prevented_calls = max(0, total_reqs - backend_calls)

    with k1:
        render_metric_card(
            title="Cache Hit Ratio",
            value=format_percentage(hit_rate),
            subtitle=f"{format_int(hits)} hits of {format_int(total_reqs)} reqs",
            tag="RETENTION",
            delta=f"Miss Rate: {format_percentage(miss_rate)}",
            delta_color=c["emerald"] if hit_rate >= 0.5 else c["amber"],
            progress_pct=hit_rate * 100.0,
            progress_color=c["emerald"] if hit_rate >= 0.5 else c["amber"],
            tooltip="Ratio of requests fulfilled directly from cache memory without backend invocation.",
        )

    with k2:
        render_metric_card(
            title="Backend Calls Shielded",
            value=format_int(prevented_calls),
            subtitle=f"{format_int(backend_calls)} actual upstream calls",
            tag="OFFLOAD",
            delta="Zero-Latency Hits",
            delta_color=c["emerald"],
            progress_pct=(prevented_calls / total_reqs * 100.0) if total_reqs > 0 else 0.0,
            progress_color=c["emerald"],
            tooltip="Total backend requests completely prevented by in-memory cache hits.",
        )

    with k3:
        render_metric_card(
            title="Avg Backend Latency",
            value=format_latency(latency_ms),
            subtitle="Observed miss penalty",
            tag="MISS COST",
            delta="Incurred on cache miss",
            delta_color=c["amber"],
            tooltip="Mean retrieval time when the cache is missed and backend database/inference is invoked.",
        )

    with k4:
        render_metric_card(
            title="Window Sample Time",
            value=format_duration(obs.get("window_seconds")),
            subtitle=f"Snapshot: {format_timestamp(obs.get('timestamp'))}",
            tag="TELEMETRY",
            delta="Read-Only Observation",
            delta_color=c["purple"],
            tooltip="Active observation window duration. Can be rotated via System > Reset Window.",
        )

    # --------------------------------------------------
    # PRACTICAL IMPACT BANNER
    # --------------------------------------------------
    shield_pct = (prevented_calls / total_reqs * 100.0) if total_reqs > 0 else 0.0
    impact_html = (
        f'<div class="hero-card" style="padding: 14px 18px; margin-top: 28px; margin-bottom: 24px; border: 1px solid {c["card_border"]}; border-left: 3px solid {c["emerald"]} !important; display: flex; justify-content: space-between; align-items: center;">'
        f'<div style="display: flex; align-items: center; gap: 10px;">'
        f'<span style="font-size: 16px;">⚡</span>'
        f'<span style="font-size: 13px; font-weight: 700; color: {c["text"]};">'
        f'System Performance Impact: Cache currently absorbing <b>{shield_pct:.1f}%</b> of request traffic.'
        f'</span>'
        f'</div>'
        f'<span class="badge-pill badge-protected">OFFLOAD ACTIVE</span>'
        f'</div>'
    )
    st.markdown(impact_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # HIT / MISS RATIO & BACKEND OFFLOAD CHARTS
    # --------------------------------------------------
    c_chart1, c_chart2 = st.columns([1.1, 1.4])

    with c_chart1:
        st.markdown(
            f'<div style="margin-bottom: 10px;">'
            f'<h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c["text"]};">'
            f'Traffic Composition'
            f'</h3>'
            f'</div>',
            unsafe_allow_html=True,
        )
        render_donut_chart(
            values=[hits, misses],
            labels=["Cache HIT", "Cache MISS"],
            title="Live HIT vs MISS",
            colors=[c["emerald"], c["rose"]],
            height=300,
        )

    with c_chart2:
        st.markdown(
            f'<div style="margin-bottom: 10px;">'
            f'<h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c["text"]};">'
            f'Backend Call Attenuation'
            f'</h3>'
            f'</div>',
            unsafe_allow_html=True,
        )
        render_comparison_bar_chart(
            categories=["Total Requests", "Backend Calls Incurred", "Calls Shielded"],
            values_dict={
                "Requests": [total_reqs, backend_calls, prevented_calls]
            },
            title="Total Ingress vs Upstream Execution",
            y_title="Request Count",
            unit="",
            height=300,
        )

    # --------------------------------------------------
    # ACTIVE KEY ACCESS FREQUENCY IN CURRENT WINDOW
    # --------------------------------------------------
    st.markdown(
        f'<div style="display: flex; justify-content: space-between; align-items: center; margin: 28px 0 10px 0;">'
        f'<h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c["text"]};">Key Access Velocity in Active Window</h3>'
        f'<span style="font-size: 11px; color: {c["text_muted"]};">From GET /telemetry/observation</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    access_counts = obs.get("current_window_access_counts", {})
    if access_counts:
        items_data = [
            {"Cache Key": k, "Access Count": v, "Relative Velocity": min(1.0, v / 50.0)}
            for k, v in sorted(access_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        df_keys = pd.DataFrame(items_data)
        st.dataframe(
            df_keys,
            column_config={
                "Cache Key": st.column_config.TextColumn("Cache Key", width="large"),
                "Access Count": st.column_config.NumberColumn("Accesses in Window", format="%d reqs"),
                "Relative Velocity": st.column_config.ProgressColumn(
                    "Window Intensity", min_value=0.0, max_value=1.0, format="%.2f"
                ),
            },
            hide_index=True,
            width="stretch",
            height=220,
        )
    else:
        st.info(
            "No key-level access traffic recorded in the active observation window yet. "
            "Use the **Simulator** tab to issue sample product or recommendation requests and observe real-time access counters."
        )
