import streamlit as st

from frontend.services.api_client import (
    get_cache_stats,
    get_adaptive_decision,
    get_workload,
    get_performance_history,
)

from frontend.components.metric_card import render_metric_card
from frontend.components.charts import render_line_chart


st.title("⚡ Cache Performance Overview")

st.caption(
    "Real-time view of workload, cache performance and adaptive behavior"
)


# --------------------------------------------------
# DATA
# --------------------------------------------------

stats = get_cache_stats()
decision = get_adaptive_decision()
workload = get_workload()
history = get_performance_history()


# --------------------------------------------------
# KPI CARDS
# --------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

with col1:
    render_metric_card(
        "Cache Hit Rate",
        f"{stats['hit_rate']}%",
        "Current hit performance",
        "🎯",
    )

with col2:
    render_metric_card(
        "Requests / Sec",
        f"{stats['requests_per_second']:,}",
        "Incoming request rate",
        "⚡",
    )

with col3:
    render_metric_card(
        "Cache Utilization",
        f"{stats['cache_usage']}%",
        "Current memory usage",
        "💾",
    )

with col4:
    render_metric_card(
        "Cached Objects",
        f"{stats['total_objects']:,}",
        "Objects currently cached",
        "📦",
    )


st.write("")


# --------------------------------------------------
# PERFORMANCE CHARTS
# --------------------------------------------------

left, right = st.columns(2)

with left:
    render_line_chart(
        history["time"],
        history["hit_rate"],
        "Cache Hit Rate",
        "Hit Rate (%)",
    )

with right:
    render_line_chart(
        history["time"],
        history["request_rate"],
        "Request Rate",
        "Requests / sec",
    )


# --------------------------------------------------
# WORKLOAD + CACHE UTILIZATION
# --------------------------------------------------

left, right = st.columns(2)

with left:
    st.subheader("Current Workload")

    st.markdown(
        f"""
        <div class="status-card">
            <div class="muted">WORKLOAD TYPE</div>
            <h2>{workload['workload_type']}</h2>

            <div style="margin-top:15px;">
                Request Rate:
                <strong>{workload['request_rate']:,} req/s</strong>
            </div>

            <div style="margin-top:8px;">
                Hit Rate:
                <strong>{workload['hit_rate']}%</strong>
            </div>

            <div style="margin-top:8px;">
                Backend Latency:
                <strong>{workload['backend_latency_ms']} ms</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with right:
    st.subheader("Cache Utilization")

    st.progress(
        min(stats["cache_usage"] / 100, 1.0)
    )

    st.metric(
        "Current Utilization",
        f"{stats['cache_usage']}%",
    )

    st.caption(
        "Adaptive engine monitors cache pressure and workload "
        "to determine capacity changes."
    )


# --------------------------------------------------
# ADAPTIVE ENGINE
# --------------------------------------------------

st.subheader("⚡ Adaptive Engine")

action = decision["capacity_action"]

if action == "SCALE_UP":
    icon = "⬆️"
elif action == "SCALE_DOWN":
    icon = "⬇️"
else:
    icon = "⏸️"


st.markdown(
    f"""
    <div class="decision-card">

        <div class="muted">
            CURRENT DECISION
        </div>

        <h2>
            {icon} {action}
        </h2>

        <p>
            {decision['reason']}
        </p>

        <hr>

        <div>
            <span class="muted">
                Recommended Capacity
            </span>
            <br>
            <strong>
                {decision['recommended_capacity_bytes'] / (1024 * 1024):.0f} MB
            </strong>
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# SYSTEM STATUS
# --------------------------------------------------

st.subheader("System Status")

col1, col2, col3 = st.columns(3)

with col1:
    st.success("🟢 Adaptive Engine — Active")

with col2:
    st.success("🟢 Cache Layer — Operational")

with col3:
    st.success("🟢 Monitoring — Connected")