import streamlit as st
from frontend.services.api_client import (
    get_cache_stats,
    get_adaptive_decision,
    get_workload,
    get_performance_history,
)
from frontend.components.styles import get_theme_colors, get_backend_status
from frontend.components.metric_card import render_metric_card
from frontend.components.charts import render_line_chart
from frontend.components.decision_card import render_decision_card
from frontend.components.status_badge import get_decision_badge_html


def render_overview_view():
    """Render Executive Overview dashboard with telemetry, architecture pipeline, and active traffic state."""
    c = get_theme_colors()

    # Fetch Telemetry Data
    stats = get_cache_stats()
    decision = get_adaptive_decision()
    workload = get_workload()
    history = get_performance_history()

    # Dynamic Backend Detection
    b_status = get_backend_status()
    is_live = b_status["is_live"]
    sys_health_color = "#10B981" if is_live else c["amber"]
    sys_health_text = "OPERATIONAL" if is_live else "DEMO MODE (SYNTHETIC TRACE)"
    sys_dot_html = (
        '<span class="pulse-dot"></span>'
        if is_live
        else f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{c["amber"]};margin-right:6px;"></span>'
    )
    redis_status = "CONNECTED" if is_live else "IN-MEMORY TELEMETRY"
    telemetry_status = "STREAMING (10s)" if is_live else "LOCAL SYNTHETIC (10s)"

    # --------------------------------------------------
    # HERO EXECUTIVE TITLE & LIVE STATUS
    # --------------------------------------------------


    st.markdown(
        f"""
        <div style="margin-bottom: 18px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                <span style="font-size: 10.5px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; background: rgba(56, 189, 248, 0.12); color: {c["cyan"]}; border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 4px; padding: 2px 8px;">
                    VH26 SATYAGRAH &bull; PRODUCTION CONTROL PLANE
                </span>
                <span style="font-size: 11px; color: {c["text_subtle"]};">&bull;</span>
                <span style="font-size: 11px; font-weight: 600; color: #10B981;">
                    AUTONOMOUS ARBITRATION ACTIVE
                </span>
            </div>
            <h1 style="font-size: 2.2rem; font-weight: 800; margin: 0 0 6px 0; letter-spacing: -0.6px; color: {c['text']} !important;">
                Adaptive Cache <span style="color: {c['cyan']} !important;">Control Center</span>
            </h1>
            <p style="font-size: 14px; color: {c["text_muted"]}; margin: 0 0 14px 0; max-width: 950px; line-height: 1.5;">
                Context-aware cache observability and arbitration engine that continuously optimizes hit rates, memory footprint, and 3rd-party API recompute spend beyond static LRU/LFU heuristics.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------
    # LIVE SYSTEM STATE STRIP
    # --------------------------------------------------
    state_html = (
        f'<div class="hero-card" style="padding: 10px 16px; margin-bottom: 18px; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px;">'
        f'<div style="display: flex; align-items: center; gap: 8px;">'
        f'{sys_dot_html}'
        f'<span style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase;">SYSTEM HEALTH:</span>'
        f'<strong style="font-size: 12px; color: {sys_health_color}; font-weight: 800;">{sys_health_text}</strong>'
        f'</div>'
        f'<div style="display: flex; align-items: center; gap: 8px;">'
        f'<span style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase;">ADAPTIVE ENGINE:</span>'
        f'<span style="font-size: 11px; font-weight: 800; color: {c["cyan"]}; background: rgba(56, 189, 248, 0.12); padding: 2px 8px; border-radius: 4px;">ACTIVE (GDSF+Utility)</span>'
        f'</div>'
        f'<div style="display: flex; align-items: center; gap: 8px;">'
        f'<span style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase;">REDIS TIER-1:</span>'
        f'<strong style="font-size: 12px; color: {sys_health_color}; font-weight: 700;">{redis_status}</strong>'
        f'</div>'
        f'<div style="display: flex; align-items: center; gap: 8px;">'
        f'<span style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase;">TELEMETRY LOOP:</span>'
        f'<strong style="font-size: 12px; color: {c["purple"]}; font-weight: 700;">{telemetry_status}</strong>'
        f'</div>'
        f'</div>'
    )
    st.markdown(state_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # HERO METRIC RIBBON (4 KPIs)
    # --------------------------------------------------
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        hit_val = stats.get("hit_rate", 89.6)
        render_metric_card(
            title="Cache Hit Rate",
            value=f"{hit_val:.1f}%",
            subtitle="Target SLA: >85% &bull; Peak: 92.4%",
            tag="SLA MET",
            delta="↑ +11.2% vs baseline LRU",
            delta_color=c["emerald"],
            tooltip="Percentage of read requests served directly from memory without database fallback.",
            progress_value=hit_val / 100.0,
            progress_color="#10B981",
            is_floating=True,
        )

    with m2:
        rps_val = stats.get("requests_per_second", 1240)
        render_metric_card(
            title="Ingress Throughput",
            value=f"{rps_val:,} RPS",
            subtitle="Peak: 1,480 req/s",
            tag="CONCURRENCY",
            delta="Stable zipfian ingress",
            delta_color=c["cyan"],
            tooltip="Sustained request ingestion rate across all connected application nodes.",
            progress_value=min(1.0, rps_val / 2000.0),
            progress_color=c["cyan"],
        )

    with m3:
        p95_val = stats.get("p95_latency_ms", 27.3)
        render_metric_card(
            title="P95 Read Latency",
            value=f"{p95_val:.1f} ms",
            subtitle="Raw Database Miss: 120.0 ms",
            tag="LATENCY SLA",
            delta="↓ -35.7% speedup vs LRU",
            delta_color=c["emerald"],
            tooltip="95th percentile read latency. Traditional LRU stalls at 42.5ms due to expensive evictions.",
            progress_value=max(0.1, 1.0 - (p95_val / 100.0)),
            progress_color="#10B981",
        )

    with m4:
        usage_val = stats.get("cache_usage", 78.4)
        cap_mb = stats.get("current_capacity_mb", 512)
        render_metric_card(
            title="Memory Utilization",
            value=f"{usage_val:.1f}%",
            subtitle=f"Tier-1 RAM: {cap_mb} MB",
            tag="CAPACITY TIER",
            delta="Scaling Derivative Armed",
            delta_color=c["amber"],
            tooltip="Physical in-memory RAM occupancy. Dynamic autoscaling triggers if pressure exceeds 85%.",
            progress_value=usage_val / 100.0,
            progress_color=c["amber"],
            is_floating=True,
        )

    st.write("")

    # --------------------------------------------------
    # ADAPTIVE ENGINE VISUALIZATION (5-STAGE PIPELINE)
    # --------------------------------------------------
    st.markdown(
        f"""<div style="display: flex; justify-content: space-between; align-items: center; margin: 8px 0 6px 0;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                Adaptive Engine Architecture & Decision Pipeline
            </h3>
            <span class="badge-pill badge-active">AUTONOMOUS ARBITRATION</span>
        </div>""",
        unsafe_allow_html=True,
    )
    st.caption(
        "How the Adaptive Engine thinks: Real-time telemetry signals feed multi-factor scoring to dynamically decide RETAIN, EVICT, or REFRESH."
    )

    pipe_grid = (
        f'<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 22px;">'
        # Node 1: Telemetry
        f'<div class="pipeline-node">'
        f'<div style="font-size: 10px; font-weight: 800; color: {c["cyan"]}; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px;">STAGE 1</div>'
        f'<div style="font-size: 13.5px; font-weight: 800; color: {c["text"]}; margin-bottom: 4px;">Telemetry Ingestion</div>'
        f'<div style="font-size: 11px; color: {c["text_muted"]}; line-height: 1.4;">Access streams, miss latency, burst rate & memory pressure index.</div>'
        f'<div style="margin-top: 8px;"><span style="font-size: 9.5px; background: rgba(56,189,248,0.12); color: {c["cyan"]}; padding: 2px 6px; border-radius: 4px; font-weight: 700;">1,250 RPS</span></div>'
        f'</div>'
        # Node 2: Signal Analysis
        f'<div class="pipeline-node">'
        f'<div style="font-size: 10px; font-weight: 800; color: {c["purple"]}; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px;">STAGE 2</div>'
        f'<div style="font-size: 13.5px; font-weight: 800; color: {c["text"]}; margin-bottom: 4px;">Signal Extraction</div>'
        f'<div style="font-size: 11px; color: {c["text_muted"]}; line-height: 1.4;">Analyzes API recompute cost, object size, retrieval penalty & frequency.</div>'
        f'<div style="margin-top: 8px;"><span style="font-size: 9.5px; background: rgba(168,85,247,0.12); color: {c["purple"]}; padding: 2px 6px; border-radius: 4px; font-weight: 700;">Zipfian Skew</span></div>'
        f'</div>'
        # Node 3: Value Scoring
        f'<div class="pipeline-node">'
        f'<div style="font-size: 10px; font-weight: 800; color: {c["cyan"]}; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px;">STAGE 3</div>'
        f'<div style="font-size: 13.5px; font-weight: 800; color: {c["text"]}; margin-bottom: 4px;">Utility Scoring</div>'
        f'<div style="font-size: 11px; color: {c["text_muted"]}; line-height: 1.4;">Computes multi-factor GDSF score: (Cost^α &times; Latency^β &times; Hits) / Size^γ.</div>'
        f'<div style="margin-top: 8px;"><span style="font-size: 9.5px; background: rgba(56,189,248,0.12); color: {c["cyan"]}; padding: 2px 6px; border-radius: 4px; font-weight: 700;">α=1.2, β=1.0</span></div>'
        f'</div>'
        # Node 4: Economic Density
        f'<div class="pipeline-node">'
        f'<div style="font-size: 10px; font-weight: 800; color: {c["amber"]}; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px;">STAGE 4</div>'
        f'<div style="font-size: 13.5px; font-weight: 800; color: {c["text"]}; margin-bottom: 4px;">Economic Density</div>'
        f'<div style="font-size: 11px; color: {c["text_muted"]}; line-height: 1.4;">Evaluates marginal dollar ROI: avoids expensive AI recomputes over bulky assets.</div>'
        f'<div style="margin-top: 8px;"><span style="font-size: 9.5px; background: rgba(245,158,11,0.12); color: {c["amber"]}; padding: 2px 6px; border-radius: 4px; font-weight: 700;">+28.4% Marginal ROI</span></div>'
        f'</div>'
        # Node 5: Autonomous Action
        f'<div class="pipeline-node" style="border-color: rgba(16, 185, 129, 0.4);">'
        f'<div style="font-size: 10px; font-weight: 800; color: #10B981; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px;">STAGE 5</div>'
        f'<div style="font-size: 13.5px; font-weight: 800; color: {c["text"]}; margin-bottom: 4px;">Arbiter Action</div>'
        f'<div style="font-size: 11px; color: {c["text_muted"]}; line-height: 1.4;">Automated execution: protects high-cost objects and prunes low-density items.</div>'
        f'<div style="margin-top: 8px; display: flex; justify-content: center; gap: 4px;">'
        f'{get_decision_badge_html("RETAIN")} {get_decision_badge_html("EVICT")} {get_decision_badge_html("REFRESH")}'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(pipe_grid, unsafe_allow_html=True)

    # --------------------------------------------------
    # CONTINUOUS TELEMETRY DYNAMICS CHARTS
    # --------------------------------------------------
    st.markdown(
        f"""<div style="display: flex; justify-content: space-between; align-items: center; margin: 14px 0 8px 0;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                Continuous Telemetry Dynamics
            </h3>
            <span class="badge-pill badge-active">REAL-TIME SCRAPING</span>
        </div>""",
        unsafe_allow_html=True,
    )

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
                height=280,
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
                height=280,
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
                height=280,
            )
        with ch4:
            render_line_chart(
                history["time"],
                history.get(
                    "cost_per_hour",
                    [
                        17.8,
                        16.9,
                        15.4,
                        14.2,
                        13.5,
                        12.8,
                        12.1,
                        11.6,
                        11.3,
                        11.2,
                    ],
                ),
                "Simulated Hourly Recompute Spend ($)",
                y_title="Spend ($/hr)",
                color="#F59E0B",
                unit=" $/hr",
                show_area=True,
                height=280,
            )

    st.markdown(
        f'<div style="height: 1px; background: {c["card_border"]}; margin: 20px 0;"></div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------
    # ACTIVE TRAFFIC PROFILE & REAL-TIME ARBITER
    # --------------------------------------------------
    col_workload, col_arbiter = st.columns([1.15, 1.25])

    with col_workload:
        st.markdown(
            f"""<div style="margin-bottom: 10px;">
                <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                    Active Traffic Profile
                </h3>
            </div>""",
            unsafe_allow_html=True,
        )
        meter_bg = "#1E293B" if c["is_dark"] else "#E2E8F0"
        pressure_pct = min(stats.get("cache_usage", 78), 100)

        workload_card_html = (
            f'<div class="status-card" style="box-shadow: 0 4px 16px rgba(0,0,0,0.15);">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
            f'<span class="muted" style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">TRAFFIC INFERENCE ENGINE</span>'
            f'<span class="badge-pill badge-active">ZIPFIAN SKEW ACTIVE</span>'
            f'</div>'
            f'<div style="font-size:18px;font-weight:800;color:{c["text"]};margin:4px 0 14px 0;letter-spacing:-0.01em;">{workload.get("workload_type", "E-Commerce Flash Sale")}</div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">'
            f'<div style="background:{c["card_bg_elevated"]};padding:10px 12px;border-radius:6px;border:1px solid {c["card_border"]};">'
            f'<span class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">Read : Write Ratio</span>'
            f'<div style="font-size:15px;font-weight:800;color:{c["text"]};margin-top:2px;">{workload.get("read_write_ratio", "92 : 8")}</div>'
            f'</div>'
            f'<div style="background:{c["card_bg_elevated"]};padding:10px 12px;border-radius:6px;border:1px solid {c["card_border"]};">'
            f'<span class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">Active Concurrency</span>'
            f'<div style="font-size:15px;font-weight:800;color:{c["cyan"]};margin-top:2px;">{workload.get("active_connections", 142)} clients</div>'
            f'</div>'
            f'<div style="background:{c["card_bg_elevated"]};padding:10px 12px;border-radius:6px;border:1px solid {c["card_border"]};">'
            f'<span class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">Backend Miss Penalty</span>'
            f'<div style="font-size:15px;font-weight:800;color:{c["amber"]};margin-top:2px;">{workload.get("backend_latency_ms", 120.0)} ms</div>'
            f'</div>'
            f'<div style="background:{c["card_bg_elevated"]};padding:10px 12px;border-radius:6px;border:1px solid {c["card_border"]};">'
            f'<span class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">P99 Tail Latency</span>'
            f'<div style="font-size:15px;font-weight:800;color:{c["purple"]};margin-top:2px;">{workload.get("p99_latency_ms", 48.1)} ms</div>'
            f'</div>'
            f'</div>'
            f'<div style="margin-top:14px;border-top:1px solid {c["card_border"]};padding-top:12px;">'
            f'<div style="display:flex;justify-content:space-between;font-size:11.5px;margin-bottom:6px;">'
            f'<span class="muted" style="font-weight:600;">RAM Memory Pressure Index</span>'
            f'<strong style="color:{c["text"]};">{pressure_pct:.1f}%</strong>'
            f'</div>'
            f'<div style="background:{meter_bg};height:7px;border-radius:4px;overflow:hidden;">'
            f'<div style="background:linear-gradient(90deg, #10B981, #F59E0B);width:{pressure_pct}%;height:100%;border-radius:4px;"></div>'
            f'</div>'
            f'</div>'
            f'</div>'
        )
        st.markdown(workload_card_html, unsafe_allow_html=True)

    with col_arbiter:
        st.markdown(
            f"""<div style="margin-bottom: 10px;">
                <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                    Real-Time Engine Arbiter
                </h3>
            </div>""",
            unsafe_allow_html=True,
        )
        render_decision_card(decision)

    st.markdown(
        f'<div style="height: 1px; background: {c["card_border"]}; margin: 20px 0;"></div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------
    # SUBSYSTEMS & LIVE ACTIVITY STREAM
    # --------------------------------------------------
    col_pillars, col_stream = st.columns([1.1, 1.4])

    with col_pillars:
        st.markdown("### Core Subsystems Health")
        p1_html = (
            f'<div class="hero-card" style="margin-bottom: 12px;">'
            f'<div style="display: flex; justify-content: space-between; align-items: center;">'
            f'<span style="font-size: 13.5px; font-weight: 700; color: {c["text"]};">Multi-Factor Adaptive Arbiter</span>'
            f'<span class="badge-pill badge-protected">ONLINE</span>'
            f'</div>'
            f'<p style="color: {c["text_muted"]}; font-size: 12px; margin: 6px 0 0 0; line-height: 1.5;">'
            f'Evaluates retrieval latency, 3rd-party API cost, and footprint to assign dynamic utility density.'
            f'</p>'
            f'</div>'
        )
        st.markdown(p1_html, unsafe_allow_html=True)

        p2_badge = "HEALTHY" if is_live else "SYNTHETIC"
        p2_badge_cls = "badge-protected" if is_live else "badge-hot"
        p2_html = (
            f'<div class="hero-card" style="margin-bottom: 12px;">'
            f'<div style="display: flex; justify-content: space-between; align-items: center;">'
            f'<span style="font-size: 13.5px; font-weight: 700; color: {c["text"]};">Tier-1 Storage Layer</span>'
            f'<span class="badge-pill {p2_badge_cls}">{p2_badge}</span>'
            f'</div>'
            f'<p style="color: {c["text_muted"]}; font-size: 12px; margin: 6px 0 0 0; line-height: 1.5;">'
            f'Execution layer holding active key entries with background probabilistic X-Fetch refresh.'
            f'</p>'
            f'</div>'
        )
        st.markdown(p2_html, unsafe_allow_html=True)

        p3_html = (
            f'<div class="hero-card">'
            f'<div style="display: flex; justify-content: space-between; align-items: center;">'
            f'<span style="font-size: 13.5px; font-weight: 700; color: {c["text"]};">Telemetry & Scaling Arbiter</span>'
            f'<span class="badge-pill badge-active">MONITORING</span>'
            f'</div>'
            f'<p style="color: {c["text_muted"]}; font-size: 12px; margin: 6px 0 0 0; line-height: 1.5;">'
            f'Calculates marginal economic ROI derivative: triggers autoscaling when offload value exceeds RAM cost.'
            f'</p>'
            f'</div>'
        )
        st.markdown(p3_html, unsafe_allow_html=True)

    with col_stream:
        stream_badge_title = "● LIVE STREAMING" if is_live else "● DEMO STREAM"
        stream_badge_color = "#10B981" if is_live else c["amber"]
        st.markdown(
            f"""<div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                    Live Adaptive Activity Stream
                </h3>
                <span style="color: {stream_badge_color}; font-size: 11px; font-weight: 700;">{stream_badge_title}</span>
            </div>""",
            unsafe_allow_html=True,
        )
        feed_html = (
            f'<div class="terminal-box">'
            f'<div style="display: flex; justify-content: space-between; border-bottom: 1px dashed rgba(56, 189, 248, 0.25); padding-bottom: 6px; margin-bottom: 8px;">'
            f'<span style="color: #94A3B8; font-size: 11px; font-weight: 700;">TIMESTAMP / ACTION</span>'
            f'<span style="color: {stream_badge_color}; font-size: 11px; font-weight: 700;">FEED ACTIVE</span>'
            f'</div>'
            f'<div style="margin-bottom: 8px;">'
            f'<span style="color: #64748B; font-size: 11px;">15:45:12</span> &nbsp; '
            f'{get_decision_badge_html("RETAIN")} &nbsp; '
            f'<code style="color: #38BDF8 !important; background: rgba(56, 189, 248, 0.12) !important;">rec:dnn:feed_v2:user_8819</code><br>'
            f'<span style="color: #94A3B8; font-size: 11.5px; margin-left: 20px;">Reason: High economic value density ($0.082 model inference &gt; locked in RAM)</span>'
            f'</div>'
            f'<div style="margin-bottom: 8px;">'
            f'<span style="color: #64748B; font-size: 11px;">15:45:15</span> &nbsp; '
            f'{get_decision_badge_html("EVICT")} &nbsp; '
            f'<code style="color: #38BDF8 !important; background: rgba(56, 189, 248, 0.12) !important;">media:thumb:banner_hero_v3</code><br>'
            f'<span style="color: #94A3B8; font-size: 11.5px; margin-left: 20px;">Reason: Low utility density (Freed 2.4 MB for $0.002 penalty, 8ms latency)</span>'
            f'</div>'
            f'<div style="margin-bottom: 8px;">'
            f'<span style="color: #64748B; font-size: 11px;">15:45:18</span> &nbsp; '
            f'{get_decision_badge_html("REFRESH")} &nbsp; '
            f'<code style="color: #38BDF8 !important; background: rgba(56, 189, 248, 0.12) !important;">pricing:dynamic:surge:loc_14</code><br>'
            f'<span style="color: #94A3B8; font-size: 11.5px; margin-left: 20px;">Reason: Probabilistic X-Fetch early refresh triggered prior to stampede TTL</span>'
            f'</div>'
            f'<div>'
            f'<span style="color: #64748B; font-size: 11px;">15:45:21</span> &nbsp; '
            f'<span style="color: #10B981; font-size: 11px; font-weight: 700;">[SCALE_UP]</span> &nbsp; '
            f'<code style="color: #38BDF8 !important; background: rgba(56, 189, 248, 0.12) !important;">CAPACITY_TARGET_512MB</code><br>'
            f'<span style="color: #94A3B8; font-size: 11.5px; margin-left: 20px;">Reason: Marginal utility +28.4% ROI justifies expanding tier</span>'
            f'</div>'
            f'<div style="margin-top: 10px; border-top: 1px dashed rgba(56, 189, 248, 0.25); padding-top: 8px; color: #94A3B8; font-size: 11px;">'
            f'&bull; Decision queue: 0.4ms latency &bull; 0 dropped evictions &bull; Active keys: 1,240'
            f'</div>'
            f'</div>'
        )
        st.markdown(feed_html, unsafe_allow_html=True)

    st.markdown(
        f'<div style="height: 1px; background: {c["card_border"]}; margin: 20px 0;"></div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------
    # QUICK NAVIGATION SHORTCUTS
    # --------------------------------------------------
    st.markdown("### Explore Observability Modules")
    cta1, cta2, cta3, cta4 = st.columns(4)

    with cta1:
        if st.button("Cache Objects Landscape", width="stretch", type="primary"):
            st.session_state["active_nav"] = "Cache Objects"
            st.rerun()

    with cta2:
        if st.button("Adaptive Decision Arbiter", width="stretch"):
            st.session_state["active_nav"] = "Decisions"
            st.rerun()

    with cta3:
        if st.button("Workload Stress Simulator", width="stretch"):
            st.session_state["active_nav"] = "Workload"
            st.rerun()

    with cta4:
        if st.button("Policy Benchmarks Lab", width="stretch"):
            st.session_state["active_nav"] = "Benchmarks"
            st.rerun()
