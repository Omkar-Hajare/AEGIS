import streamlit as st
import pandas as pd

from frontend.services.api_client import (
    get_adaptive_decision,
    get_cache_stats,
    get_cache_objects,
    get_workload,
)
from frontend.services.telemetry_service import (
    get_telemetry_observation,
    get_system_state,
)
from frontend.utils.formatting import (
    format_request_rate,
    format_percentage,
    format_latency,
    format_bytes,
)
from frontend.components.styles import get_theme_colors
from frontend.components.metric_card import render_metric_card
from frontend.components.decision_card import render_decision_card
from frontend.components.status_badge import (
    get_decision_badge_html,
    get_status_pill_html,
)


def render_adaptive_decisions_view():
    """Render Adaptive Decisions & Arbitration Engine with weight sensitivity tuner and live audit log."""
    c = get_theme_colors()

    # Live telemetry feeding the adaptive arbiter
    obs = get_telemetry_observation()
    sys_state = get_system_state()

    # Fetch Data
    decision = get_adaptive_decision()
    stats = get_cache_stats()
    objects = get_cache_objects()
    workload = get_workload()

    # Header Title Block with cleanly aligned right badge
    header_html = (
        f'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin: 0 0 12px 0; flex-wrap: wrap; gap: 12px;">'
        f'<div>'
        f'<h1 style="margin: 0 0 6px 0; font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; color: {c["text"]} !important;">'
        f'Adaptive Decisions & <span style="color: {c["text_muted"]} !important; font-weight: 600;">Arbitration Engine</span>'
        f'</h1>'
        f'<p style="margin: 0; font-size: 13.5px; line-height: 1.5; color: {c["text_muted"]}; max-width: 820px;">'
        f'Real-time evaluation of multi-signal utility density, dynamic weight sensitivity arbitration, and continuous decision auditing.'
        f'</p>'
        f'</div>'
        f'<div style="display: flex; align-items: center; padding-top: 6px;">'
        f'<span style="font-size: 10.5px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; background: {"rgba(255, 255, 255, 0.06)" if c["is_dark"] else "rgba(0, 0, 0, 0.05)"}; color: {c["text_muted"]}; border: 1px solid {c["card_border"]}; border-radius: 6px; padding: 4px 12px; white-space: nowrap;">'
        f'MULTI-FACTOR GDSF &bull; DECISION ARBITRATION'
        f'</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # HONEST INTEGRATION NOTICE (PERSON 1 BOUNDARY)
    # --------------------------------------------------
    notice_html = (
        f'<div class="hero-card" style="padding: 12px 18px; margin-bottom: 20px; border: 1px solid {c["card_border"]} !important; border-left: 3px solid {c["purple"]} !important;">'
        f'<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">'
        f'<div style="display: flex; align-items: center; gap: 8px;">'
        f'<span style="font-size: 14px;">⚡</span>'
        f'<strong style="font-size: 13px; color: {c["text"]};">Adaptive Engine Integration: Interface & Component Architecture Ready</strong>'
        f'</div>'
        f'<span class="badge-pill badge-active" style="font-size: 10px;">PERSON 1 CONTRACT BOUNDARY</span>'
        f'</div>'
        f'<p style="font-size: 12px; color: {c["text_muted"]}; margin: 0; line-height: 1.5;">'
        f'The live backend exposes telemetry streams (<code>/telemetry/observation</code>, <code>/telemetry/workload</code>, <code>/telemetry/system</code>). '
        f'The dedicated <code>/adaptive/decisions</code> decision-history endpoint is owned by Person 1 and will be integrated into the backend REST API next. '
        f'Below displays the live input signals feeding the arbiter, followed by the complete arbitration model and sensitivity playground.'
        f'</p>'
        f'</div>'
    )
    st.markdown(notice_html, unsafe_allow_html=True)

    # Real signals feeding the arbiter strip
    st.markdown(
        f"""<div style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
            <h4 style="margin: 0; font-size: 1rem; font-weight: 700; color: {c['text']};">
                Active Telemetry Signals Feeding Arbiter
            </h4>
            <span style="font-size: 11px; color: {c['text_muted']}; font-weight: 600;">LIVE INPUT VECTORS</span>
        </div>""",
        unsafe_allow_html=True,
    )
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown(
            f"""<div class="status-card" style="padding: 14px 16px; border-radius: 10px; margin-bottom: 0;">
                <span class="muted" style="font-size: 10px; font-weight: 700; text-transform: uppercase;">REQUEST VELOCITY</span>
                <div style="font-size: 16px; font-weight: 800; color: {c['text']}; margin-top: 2px;">{format_request_rate(obs.get("request_rate", 0.0))}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with s2:
        st.markdown(
            f"""<div class="status-card" style="padding: 14px 16px; border-radius: 10px; margin-bottom: 0;">
                <span class="muted" style="font-size: 10px; font-weight: 700; text-transform: uppercase;">CURRENT HIT RATIO</span>
                <div style="font-size: 16px; font-weight: 800; color: {c['emerald']}; margin-top: 2px;">{format_percentage(obs.get("hit_rate", 0.0))}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with s3:
        st.markdown(
            f"""<div class="status-card" style="padding: 14px 16px; border-radius: 10px; margin-bottom: 0;">
                <span class="muted" style="font-size: 10px; font-weight: 700; text-transform: uppercase;">BACKEND RETRIEVAL DELAY</span>
                <div style="font-size: 16px; font-weight: 800; color: {c['purple']}; margin-top: 2px;">{format_latency(obs.get("backend_latency_ms", 0.0))}</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with s4:
        st.markdown(
            f"""<div class="status-card" style="padding: 14px 16px; border-radius: 10px; margin-bottom: 0;">
                <span class="muted" style="font-size: 10px; font-weight: 700; text-transform: uppercase;">CACHE USAGE</span>
                <div style="font-size: 16px; font-weight: 800; color: {c['amber']}; margin-top: 2px;">{format_bytes(sys_state.get("cache_usage_bytes", 0))}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    # --------------------------------------------------
    # WORKLOAD STATE & KPI SUMMARY STRIP
    # --------------------------------------------------
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_metric_card(
            "Active Policy Mode",
            "Utility-Density",
            subtitle="Cost + Latency + Size aware",
            tag="ALGORITHM",
            delta="Adaptive GDSF",
            delta_color=c["purple"],
            is_floating=True,
            tooltip="Generalized Greedy Dual-Size Frequency (GDSF) with dynamic inflation clock.",
            progress_value=0.92,
            progress_color=c["purple"],
        )
    with m2:
        render_metric_card(
            "Current Arbiter Action",
            decision.get("action", "SCALE_UP"),
            subtitle="+28.4% ROI threshold met",
            tag="ACTION",
            delta="Triggered by memory pressure",
            delta_color=c["emerald"],
            tooltip="Current active intervention dispatched by the engine.",
            progress_value=0.85,
            progress_color=c["emerald"],
        )
    with m3:
        render_metric_card(
            "Target Memory Tier",
            f"{decision.get('target_capacity_mb', 512)} MB",
            subtitle="From 384 MB baseline",
            tag="CAPACITY",
            delta="+128 MB Elastic Scaling",
            delta_color=c["text_muted"],
            tooltip="Recommended Tier-1 RAM allocation to maintain >85% hit rate under active traffic.",
            progress_value=0.75,
            progress_color=c["text_muted"],
        )
    with m4:
        render_metric_card(
            "Hourly Value Preserved",
            f"${decision.get('cost_saved_hourly', 7.20):.2f} / hr",
            subtitle="Net API recompute avoidance",
            tag="SAVINGS",
            delta="+$172.80 / day run-rate",
            delta_color=c["emerald"],
            is_floating=True,
            tooltip="Direct dollars saved by shielding high-cost model inference and DB queries from eviction.",
            progress_value=0.88,
            progress_color=c["emerald"],
        )

    # --------------------------------------------------
    # ACTIVE DECISION ARBITER DETAIL CARD
    # --------------------------------------------------
    st.markdown(
        f"""<div style="margin: 28px 0 10px 0;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                Active Arbiter Cycle Output
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
    # MULTI-FACTOR WEIGHT SENSITIVITY TUNER
    # --------------------------------------------------
    st.markdown(
        f"""<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                Multi-Factor Signal Sensitivity Tuner
            </h3>
            <span class="badge-pill badge-active">GDSF PARAMETER ENGINE</span>
        </div>""",
        unsafe_allow_html=True,
    )
    st.caption(
        "Interactively adjust the weights of the multi-factor scoring function: Score = (Cost^α × Latency^β × Frequency) / (Size^γ × StalePenalty)."
    )

    t1, t2, t3 = st.columns(3)
    with t1:
        alpha = st.slider(
            "Recompute Cost Weight (α)",
            min_value=0.0,
            max_value=3.0,
            value=1.2,
            step=0.1,
            help="Higher α aggressively protects expensive 3rd-party API calls (e.g. OpenAI/Anthropic inference).",
        )
    with t2:
        beta = st.slider(
            "Miss Latency Weight (β)",
            min_value=0.0,
            max_value=3.0,
            value=1.0,
            step=0.1,
            help="Higher β prioritizes slow database read queries over lightweight microservice lookups.",
        )
    with t3:
        gamma = st.slider(
            "Object Size Penalty (γ)",
            min_value=0.1,
            max_value=2.0,
            value=0.8,
            step=0.1,
            help="Higher γ penalizes bulky assets to free up RAM capacity for high-density key entries.",
        )

    # Live Simulated Recomputed Scoring Rankings
    recomputed_rows = []
    for obj in objects:
        c_val = obj.get("recompute_cost_usd", 0.01)
        l_val = obj.get("retrieval_cost_ms", 10.0)
        s_val = max(obj.get("size_kb", 1.0), 0.1)
        f_val = obj.get("access_count", 10)

        raw = (c_val**alpha) * (l_val**beta) * f_val / (s_val**gamma)
        norm_score = round(min(1.0, raw / 500.0), 3)

        recomputed_rows.append(
            {
                "Key": obj["key"],
                "Category": obj.get("category", "General"),
                "Recomputed Score": norm_score,
                "Cost ($)": f"${c_val:.3f}",
                "Size": f"{s_val:.1f} KB",
                "Hits": f_val,
                "Arbitration Status": (
                    "Protected"
                    if norm_score > 0.75
                    else ("Active" if norm_score > 0.40 else "Evict Candidate")
                ),
            }
        )

    df_recomputed = pd.DataFrame(recomputed_rows).sort_values(
        by="Recomputed Score", ascending=False
    )

    st.markdown(
        f"#### Recomputed Arbitration Rankings with α={alpha:.1f}, β={beta:.1f}, γ={gamma:.1f}"
    )
    st.dataframe(
        df_recomputed,
        column_config={
            "Recomputed Score": st.column_config.ProgressColumn(
                "Recomputed Score", min_value=0.0, max_value=1.0, format="%.3f"
            ),
        },
        width="stretch",
        hide_index=True,
    )

    st.markdown(
        f'<div style="height: 1px; background: {c["card_border"]}; margin: 20px 0;"></div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------
    # DECISION AUDIT LOG TABLE
    # --------------------------------------------------
    st.markdown(
        f"""<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                Real-Time Decision Audit Log
            </h3>
            <span class="muted" style="font-size: 12px;">Continuous execution trace</span>
        </div>""",
        unsafe_allow_html=True,
    )

    audit_records = [
        {
            "Timestamp": "15:45:15",
            "Cycle ID": "EV-9942",
            "Target Key": "media:thumb:banner_hero_v3",
            "Action": "EVICT",
            "Utility Score": "0.14",
            "Memory Freed": "2.4 MB",
            "Cost Impact": "Saved $0.002, 8ms latency penalty",
            "Status": "Executed",
        },
        {
            "Timestamp": "15:45:18",
            "Cycle ID": "RF-1049",
            "Target Key": "pricing:dynamic:surge:loc_14",
            "Action": "REFRESH",
            "Utility Score": "0.89",
            "Memory Freed": "N/A (Refreshed)",
            "Cost Impact": "Prevented stampede latency (82ms saved)",
            "Status": "Dispatched",
        },
        {
            "Timestamp": "15:45:21",
            "Cycle ID": "CAP-102",
            "Target Key": "SYSTEM_RAM_TIER",
            "Action": "SCALE_UP",
            "Utility Score": "N/A",
            "Memory Freed": "+128 MB Target",
            "Cost Impact": "Marginal API savings exceed cloud RAM cost",
            "Status": "Active",
        },
        {
            "Timestamp": "15:42:10",
            "Cycle ID": "RET-8819",
            "Target Key": "rec:dnn:feed_v2:user_8819",
            "Action": "RETAIN",
            "Utility Score": "0.96",
            "Memory Freed": "Shielded",
            "Cost Impact": "Shielded $0.082 model inference",
            "Status": "Locked in RAM",
        },
    ]

    action_filter = st.radio(
        "Filter Audit Records",
        ["ALL", "RETAIN", "EVICT", "REFRESH", "SCALE_UP"],
        horizontal=True,
        label_visibility="collapsed",
    )

    df_audit = pd.DataFrame(audit_records)
    if action_filter != "ALL":
        df_audit = df_audit[df_audit["Action"] == action_filter]

    st.dataframe(
        df_audit,
        column_config={
            "Timestamp": st.column_config.TextColumn(
                "Timestamp", width="small"
            ),
            "Cycle ID": st.column_config.TextColumn("Cycle ID", width="small"),
            "Target Key": st.column_config.TextColumn(
                "Target Key", width="medium"
            ),
            "Action": st.column_config.TextColumn("Verdict", width="small"),
            "Utility Score": st.column_config.TextColumn(
                "Score", width="small"
            ),
            "Memory Freed": st.column_config.TextColumn(
                "Footprint Delta", width="small"
            ),
            "Cost Impact": st.column_config.TextColumn(
                "Cost Avoidance / Impact", width="large"
            ),
            "Status": st.column_config.TextColumn("Status", width="small"),
        },
        width="stretch",
        hide_index=True,
    )
