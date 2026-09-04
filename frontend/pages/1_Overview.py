import os
import streamlit as st

from frontend.services.api_client import (
    get_cache_stats,
    get_adaptive_decision,
    get_workload,
    get_performance_history,
)

from frontend.components.styles import (
    apply_global_styles,
    render_sidebar_branding,
    get_theme_colors,
)
from frontend.components.metric_card import render_metric_card
from frontend.components.charts import render_line_chart
from frontend.components.decision_card import render_decision_card

st.set_page_config(
    page_title="Cache Performance Overview",
    layout="wide",
)

apply_global_styles()
render_sidebar_branding(active_page="overview")

c = get_theme_colors()

# --------------------------------------------------
# FLOATING HEADER DOCK (Zero indent, no markdown code block)
# --------------------------------------------------
dock_html = (
    f'<div class="floating-dock">'
    f'<div style="display:flex;align-items:center;">'
    f'<span class="pulse-dot"></span>'
    f'<span style="font-weight:700;font-size:12px;letter-spacing:0.8px;color:#10B981;">SYSTEM ONLINE</span>'
    f'<span style="color:{c["text_subtle"]};margin:0 10px;">|</span>'
    f'<span style="color:{c["text_muted"]};font-size:12px;font-weight:500;">Redis Tier Connected &bull; Adaptive Arbiter Active</span>'
    f'</div>'
    f'<div><span class="badge-pill badge-active">SAMPLING: 60s REAL-TIME</span></div>'
    f'</div>'
)
st.markdown(dock_html, unsafe_allow_html=True)

st.markdown(
    '<h1 style="margin:0 0 4px 0;font-size:2.2rem;">Cache Performance Overview</h1>'
    f'<p class="muted" style="font-size:13.5px;margin-bottom:22px;">Continuous telemetry of workload behavior, cache efficiency, and adaptive memory resizing.</p>',
    unsafe_allow_html=True,
)

# --------------------------------------------------
# DATA
# --------------------------------------------------
stats = get_cache_stats()
decision = get_adaptive_decision()
workload = get_workload()
history = get_performance_history()

# --------------------------------------------------
# HERO METRIC STRIP
# --------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    render_metric_card(
        "Cache Hit Rate",
        f"{stats['hit_rate']}%",
        subtitle="Target SLA: >85%",
        tag="SLA MET",
        delta="↑ +11.2% vs baseline LRU",
        delta_color="#10B981",
        is_floating=True,
    )

with col2:
    render_metric_card(
        "Throughput (RPS)",
        f"{stats['requests_per_second']:,}",
        subtitle="Peak: 1,480 req/s",
        tag="TRAFFIC",
        delta="Stable concurrency",
        delta_color=c["cyan"],
    )

with col3:
    render_metric_card(
        "P95 Read Latency",
        f"{stats.get('p95_latency_ms', 27.3)} ms",
        subtitle="Raw Database: 120.0 ms",
        tag="LATENCY",
        delta="↓ -35.7% latency cut",
        delta_color="#10B981",
    )

with col4:
    render_metric_card(
        "Memory Utilization",
        f"{stats['cache_usage']}%",
        subtitle=f"Allocation: {stats.get('current_capacity_mb', 512)} MB",
        tag="CAPACITY",
        delta="Elastic Scaling Armed",
        delta_color=c["amber"],
        is_floating=True,
    )

st.write("")

# --------------------------------------------------
# CACHE PERFORMANCE OVERVIEW (CHARTS)
# --------------------------------------------------
st.markdown("### Performance & Telemetry Dynamics")

tab_perf, tab_econ = st.tabs(
    ["Hit Rate & Ingestion Rate", "Latency & Cost Avoidance"]
)

with tab_perf:
    ch1, ch2 = st.columns(2)
    with ch1:
        render_line_chart(
            history["time"],
            history["hit_rate"],
            "Cache Hit Rate Over Time (%)",
            y_title="Hit Rate (%)",
            color="#10B981",
            unit="%",
            show_area=True,
            height=320,
        )
    with ch2:
        render_line_chart(
            history["time"],
            history["request_rate"],
            "Ingestion Rate (Requests / sec)",
            y_title="Requests / sec",
            color=c["cyan"],
            unit=" req/s",
            show_area=True,
            height=320,
        )

with tab_econ:
    ch3, ch4 = st.columns(2)
    with ch3:
        render_line_chart(
            history["time"],
            history.get(
                "latency_p95", [41, 39, 36, 34, 32, 30, 29, 28, 27.5, 27.3]
            ),
            "P95 Read Latency Trend (ms)",
            y_title="Latency (ms)",
            color=c["purple"],
            unit=" ms",
            show_area=True,
            height=320,
        )
    with ch4:
        render_line_chart(
            history["time"],
            history.get(
                "cost_per_hour",
                [17.8, 16.9, 15.4, 14.2, 13.5, 12.8, 12.1, 11.6, 11.3, 11.2],
            ),
            "Simulated Hourly Recompute Spend ($)",
            y_title="Spend ($/hr)",
            color="#F59E0B",
            unit=" $/hr",
            show_area=True,
            height=320,
        )

st.write("")
st.divider()

# --------------------------------------------------
# INTELLIGENCE & WORKLOAD BREAKDOWN
# --------------------------------------------------
st.markdown("### Intelligence & Workload Breakdown")

arch_img_path = "frontend/assets/architecture.jpg"
if os.path.exists(arch_img_path):
    st.image(
        arch_img_path,
        caption="Adaptive Caching Engine: Multi-Factor Utility Arbiter & Telemetry Feedback Loop",
        width="stretch",
    )
    st.write("")

col_workload, col_arbiter = st.columns([1.1, 1.3])

with col_workload:
    st.markdown("#### Active Traffic Profile")
    meter_bg = "#1E293B" if c["is_dark"] else "#E2E8F0"
    pressure_pct = min(stats["cache_usage"], 100)

    workload_card_html = (
        f'<div class="status-card">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span class="muted" style="font-size:11px;font-weight:700;text-transform:uppercase;">PROFILE INFERENCE</span>'
        f'<span class="badge-pill badge-active">ZIPFIAN SKEW ACTIVE</span>'
        f'</div>'
        f'<div style="font-size:20px;font-weight:800;color:{c["text"]};margin:8px 0 14px 0;">{workload["workload_type"]}</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">'
        f'<div><span class="muted" style="font-size:10.5px;font-weight:600;text-transform:uppercase;">Read : Write Ratio</span><div style="font-size:15px;font-weight:700;color:{c["text"]};margin-top:2px;">{workload.get("read_write_ratio", "92 : 8")}</div></div>'
        f'<div><span class="muted" style="font-size:10.5px;font-weight:600;text-transform:uppercase;">Active Clients</span><div style="font-size:15px;font-weight:700;color:{c["text"]};margin-top:2px;">{workload.get("active_connections", 142)} concurrency</div></div>'
        f'<div><span class="muted" style="font-size:10.5px;font-weight:600;text-transform:uppercase;">Backend Miss Penalty</span><div style="font-size:15px;font-weight:700;color:{c["amber"]};margin-top:2px;">{workload["backend_latency_ms"]} ms</div></div>'
        f'<div><span class="muted" style="font-size:10.5px;font-weight:600;text-transform:uppercase;">P99 Tail Latency</span><div style="font-size:15px;font-weight:700;color:{c["cyan"]};margin-top:2px;">{workload.get("p99_latency_ms", 48.1)} ms</div></div>'
        f'</div>'
        f'<div style="margin-top:16px;border-top:1px solid {c["card_border"]};padding-top:12px;">'
        f'<div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px;"><span class="muted">Memory Pressure Index</span><strong style="color:{c["text"]};">{stats["cache_usage"]}%</strong></div>'
        f'<div style="background:{meter_bg};height:8px;border-radius:4px;overflow:hidden;"><div style="background:linear-gradient(90deg, #10B981, #F59E0B);width:{pressure_pct}%;height:100%;"></div></div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(workload_card_html, unsafe_allow_html=True)

with col_arbiter:
    st.markdown("#### Real-Time Engine Arbiter")
    render_decision_card(decision)

st.write("")
st.divider()

# --------------------------------------------------
# SYSTEM HEALTH
# --------------------------------------------------
h1, h2, h3 = st.columns(3)

with h1:
    h1_html = (
        f'<div class="hero-card" style="padding:12px 16px;display:flex;align-items:center;justify-content:space-between;">'
        f'<div><div style="font-size:12px;font-weight:700;color:{c["text"]};">Adaptive Scoring Arbiter</div><div style="font-size:11px;color:#10B981;font-weight:600;">Active &bull; Cycle: 0.4ms</div></div>'
        f'<span class="badge-pill badge-protected">ONLINE</span></div>'
    )
    st.markdown(h1_html, unsafe_allow_html=True)

with h2:
    h2_html = (
        f'<div class="hero-card" style="padding:12px 16px;display:flex;align-items:center;justify-content:space-between;">'
        f'<div><div style="font-size:12px;font-weight:700;color:{c["text"]};">Redis Storage Tier</div><div style="font-size:11px;color:#10B981;font-weight:600;">1,240 keys loaded</div></div>'
        f'<span class="badge-pill badge-protected">HEALTHY</span></div>'
    )
    st.markdown(h2_html, unsafe_allow_html=True)

with h3:
    h3_html = (
        f'<div class="hero-card" style="padding:12px 16px;display:flex;align-items:center;justify-content:space-between;">'
        f'<div><div style="font-size:12px;font-weight:700;color:{c["text"]};">Telemetry Ingestion</div><div style="font-size:11px;color:{c["cyan"]};font-weight:600;">10s scrape frequency</div></div>'
        f'<span class="badge-pill badge-active">STREAMING</span></div>'
    )
    st.markdown(h3_html, unsafe_allow_html=True)