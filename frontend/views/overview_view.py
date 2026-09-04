import streamlit as st
import pandas as pd

from frontend.services.api_client import check_health
from frontend.services.telemetry_service import (
    get_telemetry_observation,
    get_workload_state,
    get_system_state,
)
from frontend.utils.formatting import (
    format_percentage,
    format_latency,
    format_request_rate,
    format_bytes,
    format_int,
    format_duration,
    format_timestamp,
)
from frontend.components.styles import get_theme_colors, is_dark_mode
from frontend.components.metric_card import render_metric_card
from frontend.components.charts import render_donut_chart
from frontend.components.status_badge import get_decision_badge_html


def render_overview_view():
    """Render Executive Control Center with real FastAPI telemetry and honest system indicators."""
    c = get_theme_colors()

    # Fetch live telemetry from FastAPI backend
    health = check_health()
    is_live = health.get("status") == "ok"

    obs = get_telemetry_observation()
    workload = get_workload_state()
    system = get_system_state()

    # System Health Badge Info
    sys_health_color = "#10B981" if is_live else c["amber"]
    sys_health_text = "OPERATIONAL (FASTAPI LIVE)" if is_live else "DISCONNECTED (DEMO / MOCK TRACE)"
    sys_dot_html = (
        '<span class="pulse-dot"></span>'
        if is_live
        else f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{c["amber"]};margin-right:6px;"></span>'
    )
    api_endpoint = "http://localhost:8000"

    # --------------------------------------------------
    # HERO EXECUTIVE HEADER
    # --------------------------------------------------
    st.markdown(
        f"""
        <div style="margin-bottom: 18px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                <span style="font-size: 10.5px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; background: rgba(56, 189, 248, 0.12); color: {c["cyan"]}; border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 4px; padding: 2px 8px;">
                    VH26 SATYAGRAH &bull; OBSERVABILITY CONTROL PLANE
                </span>
                <span style="font-size: 11px; color: {c["text_subtle"]};">&bull;</span>
                <span style="font-size: 11px; font-weight: 600; color: #10B981;">
                    ADAPTIVE ARBITRATION ACTIVE
                </span>
            </div>
            <h1 style="font-size: 2.2rem; font-weight: 800; margin: 0 0 6px 0; letter-spacing: -0.6px; color: {c['text']} !important;">
                Adaptive Cache <span style="color: {c['cyan']} !important;">Control Center</span>
            </h1>
            <p style="font-size: 14px; color: {c["text_muted"]}; margin: 0 0 14px 0; max-width: 950px; line-height: 1.5;">
                A context-aware, cost-driven caching engine moving beyond static LRU/LFU heuristics. 
                Observes workload signals, dynamically optimizes hit ratios, minimizes backend recomputations, and measures impact in real time.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------
    # LIVE TELEMETRY STATUS STRIP
    # --------------------------------------------------
    window_sec = obs.get("window_seconds", 0.0)
    window_str = format_duration(window_sec)
    ts_str = format_timestamp(obs.get("timestamp"))

    state_html = (
        f'<div class="hero-card" style="padding: 10px 16px; margin-bottom: 18px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px;">'
        f'<div style="display: flex; align-items: center; gap: 8px;">'
        f'{sys_dot_html}'
        f'<span style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase;">BACKEND STATUS:</span>'
        f'<strong style="font-size: 12px; color: {sys_health_color}; font-weight: 800;">{sys_health_text}</strong>'
        f'</div>'
        f'<div style="display: flex; align-items: center; gap: 8px;">'
        f'<span style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase;">SOURCE:</span>'
        f'<span style="font-size: 11px; font-weight: 700; color: {c["cyan"]}; background: rgba(56, 189, 248, 0.12); padding: 2px 8px; border-radius: 4px;">GET /telemetry/observation</span>'
        f'</div>'
        f'<div style="display: flex; align-items: center; gap: 8px;">'
        f'<span style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase;">WINDOW DURATION:</span>'
        f'<strong style="font-size: 12px; color: {c["purple"]}; font-weight: 700;">{window_str}</strong>'
        f'</div>'
        f'<div style="display: flex; align-items: center; gap: 8px;">'
        f'<span style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase;">LAST SYNC:</span>'
        f'<strong style="font-size: 12px; color: {c["text_subtle"]}; font-weight: 600;">{ts_str}</strong>'
        f'</div>'
        f'</div>'
    )
    st.markdown(state_html, unsafe_allow_html=True)

    # Cold Start Demo CTA if zero requests in current window
    total_reqs = obs.get("total_requests", 0)
    if total_reqs == 0:
        st.info(
            "💡 **Current observation window has 0 requests.** "
            "Switch to the **Simulator** tab to issue live product/recommendation requests and observe real-time MISS → HIT performance!"
        )

    # --------------------------------------------------
    # 6-KPI FIRST-CLASS OBSERVABILITY ROW
    # --------------------------------------------------
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    hit_rate = obs.get("hit_rate", 0.0)
    miss_rate = obs.get("miss_rate", 0.0)
    req_rate = obs.get("request_rate", 0.0)
    latency_ms = obs.get("backend_latency_ms", 0.0)
    backend_calls = obs.get("backend_calls", 0)
    object_count = system.get("object_count", 0)
    usage_bytes = system.get("cache_usage_bytes", 0)

    with k1:
        render_metric_card(
            title="Cache Hit Rate",
            value=format_percentage(hit_rate),
            subtitle=f"{obs.get('cache_hits', 0)} hits / {total_reqs} reqs",
            tag="PRIMARY SLA",
            tooltip="Ratio of requests served directly from cache without hitting the persistent backend store.",
            progress_value=min(1.0, max(0.0, float(hit_rate))),
            progress_color="#10B981",
            is_floating=True,
        )

    with k2:
        render_metric_card(
            title="Cache Miss Rate",
            value=format_percentage(miss_rate),
            subtitle=f"{obs.get('cache_misses', 0)} misses recorded",
            tag="PENALTY",
            tooltip="Ratio of requests requiring expensive backend recompute and retrieval.",
            progress_value=min(1.0, max(0.0, float(miss_rate))),
            progress_color=c["amber"] if miss_rate > 0.3 else c["cyan"],
        )

    with k3:
        render_metric_card(
            title="Request Rate",
            value=format_request_rate(req_rate),
            subtitle=f"Window: {window_str}",
            tag="INGRESS",
            tooltip="Total ingress request velocity in the current sliding observation window.",
            progress_value=min(1.0, float(req_rate) / 10.0) if req_rate > 0 else 0.05,
            progress_color=c["cyan"],
        )

    with k4:
        render_metric_card(
            title="Backend Latency",
            value=format_latency(latency_ms),
            subtitle="Observed retrieval delay",
            tag="LATENCY",
            tooltip="Observed time required by the backend to fetch or recompute missing items.",
            progress_value=min(1.0, float(latency_ms) / 150.0) if latency_ms > 0 else 0.1,
            progress_color=c["purple"],
        )

    with k5:
        render_metric_card(
            title="Backend Calls",
            value=format_int(backend_calls),
            subtitle="Persistent DB accesses",
            tag="OFFLOAD",
            tooltip="Number of times the backend data layer had to be queried due to cache misses.",
            progress_value=min(1.0, float(backend_calls) / max(1.0, float(total_reqs))) if total_reqs > 0 else 0.0,
            progress_color=c["amber"] if backend_calls > 5 else c["cyan"],
        )

    with k6:
        render_metric_card(
            title="Cache Footprint",
            value=format_bytes(usage_bytes),
            subtitle=f"{format_int(object_count)} cached objects",
            tag="MEMORY",
            tooltip="Total memory bytes and object count tracked in backend cache.",
            progress_value=0.25,
            progress_color=c["cyan"],
        )

    st.write("")

    # --------------------------------------------------
    # CACHE EFFICIENCY & TELEMETRY BREAKDOWN
    # --------------------------------------------------
    col_chart, col_state = st.columns([1.1, 1.4])

    with col_chart:
        st.markdown(
            f"""<div style="margin-bottom: 8px;">
                <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                    Current Window HIT vs MISS Distribution
                </h3>
            </div>""",
            unsafe_allow_html=True,
        )
        hits_cnt = obs.get("cache_hits", 0)
        misses_cnt = obs.get("cache_misses", 0)

        if hits_cnt == 0 and misses_cnt == 0:
            st.markdown(
                f"""
                <div class="status-card" style="text-align: center; padding: 40px 20px;">
                    <div style="font-size: 32px; margin-bottom: 8px;">📊</div>
                    <div style="font-size: 14px; font-weight: 700; color: {c['text']}; margin-bottom: 4px;">
                        No Requests in Current Window
                    </div>
                    <div style="font-size: 12px; color: {c['text_muted']}; max-width: 320px; margin: 0 auto 16px auto;">
                        Issue a request from the Request Simulator to view live HIT vs MISS ratio.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            render_donut_chart(
                values=[hits_cnt, misses_cnt],
                labels=["Cache HIT", "Cache MISS"],
                title="Cache Traffic Distribution",
                colors=[c["emerald"], c["rose"]],
                height=260,
            )

    with col_state:
        st.markdown(
            f"""<div style="margin-bottom: 8px;">
                <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                    Workload & System State
                </h3>
            </div>""",
            unsafe_allow_html=True,
        )

        workload_type = workload.get("workload_type")
        workload_display = workload_type if workload_type else "Not classified yet"
        workload_badge = "CLASSIFIED" if workload_type else "INFERENCE PENDING"
        workload_badge_cls = "badge-active" if workload_type else "badge-hot"

        cap_bytes = system.get("cache_capacity_bytes")
        cap_display = format_bytes(cap_bytes) if cap_bytes is not None else "Unconstrained / not configured"
        evictions = system.get("cache_evictions", 0)

        sys_card_html = (
            f'<div class="status-card">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">'
            f'<span class="muted" style="font-size:11px;font-weight:700;text-transform:uppercase;">WORKLOAD CLASSIFIER (GET /telemetry/workload)</span>'
            f'<span class="badge-pill {workload_badge_cls}">{workload_badge}</span>'
            f'</div>'
            f'<div style="font-size:17px;font-weight:800;color:{c["text"]};margin-bottom:12px;">{workload_display}</div>'
            f'<div style="display:grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px;">'
            f'<div style="background:{c["card_bg_elevated"]};padding:8px 12px;border-radius:6px;border:1px solid {c["card_border"]};">'
            f'<span class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">Observed Window</span>'
            f'<div style="font-size:14px;font-weight:700;color:{c["text"]};margin-top:2px;">{window_str}</div>'
            f'</div>'
            f'<div style="background:{c["card_bg_elevated"]};padding:8px 12px;border-radius:6px;border:1px solid {c["card_border"]};">'
            f'<span class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">Cache Evictions</span>'
            f'<div style="font-size:14px;font-weight:700;color:{c["cyan"]};margin-top:2px;">{format_int(evictions)}</div>'
            f'</div>'
            f'<div style="background:{c["card_bg_elevated"]};padding:8px 12px;border-radius:6px;border:1px solid {c["card_border"]};">'
            f'<span class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">Allocated Capacity</span>'
            f'<div style="font-size:13px;font-weight:700;color:{c["amber"] if cap_bytes is None else c["text"]};margin-top:2px;">{cap_display}</div>'
            f'</div>'
            f'<div style="background:{c["card_bg_elevated"]};padding:8px 12px;border-radius:6px;border:1px solid {c["card_border"]};">'
            f'<span class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">Backend Calls Prevented</span>'
            f'<div style="font-size:14px;font-weight:700;color:#10B981;margin-top:2px;">{format_int(hits_cnt)}</div>'
            f'</div>'
            f'</div>'
            f'<div style="font-size:11.5px;color:{c["text_muted"]};line-height:1.4;border-top:1px solid {c["card_border"]};padding-top:10px;">'
            f'<strong>Practical Impact:</strong> Caching eliminated <strong>{format_int(hits_cnt)}</strong> expensive backend recomputations. '
            f'Each cache hit avoids ~{format_latency(latency_ms)} of downstream latency.'
            f'</div>'
            f'</div>'
        )
        st.markdown(sys_card_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # ACTIVE OBJECTS IN CURRENT WINDOW
    # --------------------------------------------------
    access_counts = obs.get("current_window_access_counts", {})
    if access_counts:
        st.markdown(
            f"""<div style="margin: 18px 0 8px 0; display:flex; justify-content:space-between; align-items:center;">
                <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                    Active Access Keys in Current Observation Window
                </h3>
                <span class="badge-pill badge-active" style="font-size:10px;">LIVE KEY VELOCITY</span>
            </div>""",
            unsafe_allow_html=True,
        )
        key_cols = st.columns(min(4, len(access_counts)))
        for i, (k, cnt) in enumerate(sorted(access_counts.items(), key=lambda x: x[1], reverse=True)[:4]):
            with key_cols[i % len(key_cols)]:
                st.markdown(
                    f"""
                    <div class="hero-card" style="padding: 10px 14px;">
                        <div style="font-size: 10px; font-weight: 700; color: {c['text_muted']}; text-transform: uppercase;">KEY</div>
                        <code style="font-size: 12.5px; color: {c['cyan']} !important; background: rgba(56,189,248,0.1) !important; padding: 2px 6px; border-radius: 4px;">{k}</code>
                        <div style="margin-top: 6px; font-size: 12px; font-weight: 800; color: {c['text']};">
                            {format_int(cnt)} accesses
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # --------------------------------------------------
    # ADAPTIVE ENGINE CONCEPT & DECISION PIPELINE
    # --------------------------------------------------
    st.markdown(
        f"""<div style="display: flex; justify-content: space-between; align-items: center; margin: 20px 0 6px 0;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                Adaptive Cache Engine Architecture & Arbitration Pipeline
            </h3>
            <span class="badge-pill badge-active">AUTONOMOUS ARBITRATION</span>
        </div>""",
        unsafe_allow_html=True,
    )
    st.caption(
        "Observe → Understand workload → Adapt cache behavior → Measure impact. Telemetry signals continuously feed the multi-factor scoring arbiter."
    )

    pipe_grid = (
        f'<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 22px;">'
        f'<div class="pipeline-node">'
        f'<div style="font-size: 10px; font-weight: 800; color: {c["cyan"]}; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px;">STAGE 1</div>'
        f'<div style="font-size: 13.5px; font-weight: 800; color: {c["text"]}; margin-bottom: 4px;">Telemetry Ingestion</div>'
        f'<div style="font-size: 11px; color: {c["text_muted"]}; line-height: 1.4;">Live access streams, miss latency, burst rate & memory usage.</div>'
        f'<div style="margin-top: 8px;"><span style="font-size: 9.5px; background: rgba(56,189,248,0.12); color: {c["cyan"]}; padding: 2px 6px; border-radius: 4px; font-weight: 700;">{format_request_rate(req_rate)}</span></div>'
        f'</div>'
        f'<div class="pipeline-node">'
        f'<div style="font-size: 10px; font-weight: 800; color: {c["purple"]}; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px;">STAGE 2</div>'
        f'<div style="font-size: 13.5px; font-weight: 800; color: {c["text"]}; margin-bottom: 4px;">Workload Classifier</div>'
        f'<div style="font-size: 11px; color: {c["text_muted"]}; line-height: 1.4;">Evaluates access skew, read/write patterns, and burst dynamics.</div>'
        f'<div style="margin-top: 8px;"><span style="font-size: 9.5px; background: rgba(168,85,247,0.12); color: {c["purple"]}; padding: 2px 6px; border-radius: 4px; font-weight: 700;">{workload_display}</span></div>'
        f'</div>'
        f'<div class="pipeline-node">'
        f'<div style="font-size: 10px; font-weight: 800; color: {c["cyan"]}; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px;">STAGE 3</div>'
        f'<div style="font-size: 13.5px; font-weight: 800; color: {c["text"]}; margin-bottom: 4px;">Utility Scoring (GDSF)</div>'
        f'<div style="font-size: 11px; color: {c["text_muted"]}; line-height: 1.4;">Computes density score: (Cost^α &times; Latency^β &times; Frequency) / Size^γ.</div>'
        f'<div style="margin-top: 8px;"><span style="font-size: 9.5px; background: rgba(56,189,248,0.12); color: {c["cyan"]}; padding: 2px 6px; border-radius: 4px; font-weight: 700;">α=1.0, β=1.0, γ=1.0</span></div>'
        f'</div>'
        f'<div class="pipeline-node">'
        f'<div style="font-size: 10px; font-weight: 800; color: {c["amber"]}; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px;">STAGE 4</div>'
        f'<div style="font-size: 13.5px; font-weight: 800; color: {c["text"]}; margin-bottom: 4px;">Economic Density</div>'
        f'<div style="font-size: 11px; color: {c["text_muted"]}; line-height: 1.4;">Balances RAM cost against downstream backend recomputation penalty.</div>'
        f'<div style="margin-top: 8px;"><span style="font-size: 9.5px; background: rgba(245,158,11,0.12); color: {c["amber"]}; padding: 2px 6px; border-radius: 4px; font-weight: 700;">Latency Savings: {format_latency(latency_ms)}</span></div>'
        f'</div>'
        f'<div class="pipeline-node" style="border-color: rgba(16, 185, 129, 0.4);">'
        f'<div style="font-size: 10px; font-weight: 800; color: #10B981; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px;">STAGE 5</div>'
        f'<div style="font-size: 13.5px; font-weight: 800; color: {c["text"]}; margin-bottom: 4px;">Arbiter Action</div>'
        f'<div style="font-size: 11px; color: {c["text_muted"]}; line-height: 1.4;">Automated execution: retains high-utility entries, evicts cold items.</div>'
        f'<div style="margin-top: 8px; display: flex; justify-content: center; gap: 4px;">'
        f'{get_decision_badge_html("RETAIN")} {get_decision_badge_html("EVICT")} {get_decision_badge_html("REFRESH")}'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(pipe_grid, unsafe_allow_html=True)

    # --------------------------------------------------
    # QUICK DEMO CTA BUTTONS
    # --------------------------------------------------
    st.markdown(
        f'<div style="height: 1px; background: {c["card_border"]}; margin: 20px 0;"></div>',
        unsafe_allow_html=True,
    )
    st.markdown("### Quick Navigation & Jury Demo Shortcuts")
    cta1, cta2, cta3, cta4 = st.columns(4)

    with cta1:
        if st.button("⚡ Request Simulator (MISS → HIT)", width="stretch", type="primary"):
            st.session_state["active_nav"] = "Simulator"
            st.rerun()

    with cta2:
        if st.button("📊 Cache Performance Details", width="stretch"):
            st.session_state["active_nav"] = "Performance"
            st.rerun()

    with cta3:
        if st.button("⚙️ System State & Window Reset", width="stretch"):
            st.session_state["active_nav"] = "System"
            st.rerun()

    with cta4:
        if st.button("🏆 Policy Benchmarks Lab", width="stretch"):
            st.session_state["active_nav"] = "Benchmarks"
            st.rerun()
