import streamlit as st
import pandas as pd

from frontend.services.telemetry_service import (
    get_workload_state,
    get_telemetry_observation,
)
from frontend.services.api_client import check_health
from frontend.utils.formatting import (
    format_percentage,
    format_latency,
    format_request_rate,
    format_duration,
    format_timestamp,
    format_int,
)
from frontend.components.styles import get_theme_colors
from frontend.components.metric_card import render_metric_card


def render_workload_view():
    """Render Workload Observability with live GET /telemetry/workload signals, classification, and access profiling."""
    c = get_theme_colors()

    # Fetch live telemetry
    health = check_health()
    is_live = health.get("status") == "ok"

    workload = get_workload_state()
    obs = get_telemetry_observation()

    # Header Title Block
    header_html = (
        f'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin: 0 0 12px 0; flex-wrap: wrap; gap: 12px;">'
        f'<div>'
        f'<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">'
        f'<span style="font-size: 10px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; background: {"rgba(255, 255, 255, 0.06)" if c["is_dark"] else "rgba(0, 0, 0, 0.05)"}; color: {c["text_muted"]}; border: 1px solid {c["card_border"]}; border-radius: 4px; padding: 2px 8px;">'
        f'GET /telemetry/workload &bull; REST API CONTRACT'
        f'</span>'
        f'</div>'
        f'<h1 style="margin: 0 0 6px 0; font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; color: {c["text"]} !important;">'
        f'Workload <span style="color: {c["text_muted"]} !important; font-weight: 600;">Observability & Dynamics</span>'
        f'</h1>'
        f'<p style="margin: 0; font-size: 13.5px; line-height: 1.5; color: {c["text_muted"]}; max-width: 850px;">'
        f'Live observation of ingress request rate, cache hit/miss distributions, downstream latency penalties, and traffic classification.'
        f'</p>'
        f'</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # WORKLOAD OBSERVABILITY EXPLANATORY PANEL (MANDATORY SPEC)
    # --------------------------------------------------
    expl_panel_html = (
        f'<div class="hero-card" style="padding: 14px 18px; margin-bottom: 20px; border: 1px solid {c["card_border"]} !important;">'
        f'<div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">'
        f'<span style="font-size: 15px;">🔍</span>'
        f'<strong style="font-size: 13.5px; color: {c["text"]};">Signal Observation Framework</strong>'
        f'</div>'
        f'<p style="font-size: 12.5px; color: {c["text_muted"]}; margin: 0; line-height: 1.5;">'
        f'The system observes <strong>request rate</strong>, <strong>cache hit/miss behavior</strong>, '
        f'<strong>backend latency</strong> and <strong>access patterns</strong> to understand workload behavior.'
        f'</p>'
        f'</div>'
    )
    st.markdown(expl_panel_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # LIVE WORKLOAD KPI ROW
    # --------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)

    req_rate = workload.get("request_rate", obs.get("request_rate", 0.0))
    hit_rate = workload.get("hit_rate", obs.get("hit_rate", 0.0))
    miss_rate = workload.get("miss_rate", obs.get("miss_rate", 0.0))
    latency_ms = workload.get("backend_latency_ms", obs.get("backend_latency_ms", 0.0))
    window_sec = workload.get("window_seconds", obs.get("window_seconds", 0.0))
    timestamp = workload.get("timestamp", obs.get("timestamp"))

    with k1:
        render_metric_card(
            title="Request Ingress Rate",
            value=format_request_rate(req_rate),
            subtitle=f"Observed window: {format_duration(window_sec)}",
            tag="VELOCITY",
            tooltip="Live request ingestion rate computed over sliding observation window.",
            progress_value=min(1.0, float(req_rate) / 10.0) if req_rate > 0 else 0.05,
            progress_color=c["emerald"],
            is_floating=True,
        )

    with k2:
        render_metric_card(
            title="Cache Hit Rate",
            value=format_percentage(hit_rate),
            subtitle=f"{format_percentage(miss_rate)} miss rate",
            tag="HIT RATIO",
            tooltip="Proportion of incoming requests satisfied directly by the cache.",
            progress_value=min(1.0, max(0.0, float(hit_rate))),
            progress_color=c["emerald"],
        )

    with k3:
        render_metric_card(
            title="Cache Miss Rate",
            value=format_percentage(miss_rate),
            subtitle="Backend round-trips",
            tag="MISS RATIO",
            tooltip="Proportion of requests that missed cache and hit the database/recompute layer.",
            progress_value=min(1.0, max(0.0, float(miss_rate))),
            progress_color=c["rose"],
        )

    with k4:
        render_metric_card(
            title="Backend Miss Latency",
            value=format_latency(latency_ms),
            subtitle="Downstream penalty",
            tag="LATENCY",
            tooltip="Measured execution duration for retrieving or computing missed keys.",
            progress_value=min(1.0, float(latency_ms) / 150.0) if latency_ms > 0 else 0.1,
            progress_color=c["purple"],
            is_floating=True,
        )

    # --------------------------------------------------
    # WORKLOAD CLASSIFICATION CARD (HONEST NULL HANDLING)
    # --------------------------------------------------
    workload_type = workload.get("workload_type")
    raw_metrics = workload.get("metrics")

    # Strict compliance rule: If workload_type is null, display "Not classified yet". Never fabricate.
    has_classification = workload_type is not None and str(workload_type).strip() != ""
    classification_display = str(workload_type) if has_classification else "Not classified yet"
    status_tag = "ACTIVE CLASSIFICATION" if has_classification else "INFERENCE ENGINE PENDING"
    status_color = c["emerald"] if has_classification else c["amber"]
    badge_cls = "badge-active" if has_classification else "badge-hot"

    col_class, col_meta = st.columns([1.3, 1.0])

    with col_class:
        class_html = (
            f'<div class="status-card" style="box-shadow: 0 4px 16px rgba(0,0,0,0.12);">'
            f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">'
            f'<span class="muted" style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">WORKLOAD INFERENCE STATUS</span>'
            f'<span class="badge-pill {badge_cls}">{status_tag}</span>'
            f'</div>'
            f'<div style="font-size: 22px; font-weight: 800; color: {c["text"]}; margin: 4px 0 10px 0; letter-spacing: -0.01em;">'
            f'{classification_display}'
            f'</div>'
            f'<p style="font-size: 12.5px; color: {c["text_muted"]}; line-height: 1.5; margin: 0 0 16px 0;">'
        )

        if has_classification:
            class_html += (
                f'The backend classifier evaluated window access velocity and categorized active traffic as '
                f'<strong style="color:{c["text"]};">{classification_display}</strong>.'
            )
        else:
            class_html += (
                f'The backend classification engine has not yet classified this observation window. '
                f'In accordance with specification guidelines, the system displays <em>Not classified yet</em> '
                f'rather than fabricating a synthetic workload label.'
            )

        class_html += (
            f'</p>'
            f'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; border-top: 1px solid {c["card_border"]}; padding-top: 12px;">'
            f'<div style="background:{c["card_bg_elevated"]}; padding: 8px 12px; border-radius: 6px; border: 1px solid {c["card_border"]};">'
            f'<span class="muted" style="font-size:10px; font-weight:700; text-transform:uppercase;">Observed Window</span>'
            f'<div style="font-size: 14px; font-weight: 700; color: {c["text"]}; margin-top: 2px;">{format_duration(window_sec)}</div>'
            f'</div>'
            f'<div style="background:{c["card_bg_elevated"]}; padding: 8px 12px; border-radius: 6px; border: 1px solid {c["card_border"]};">'
            f'<span class="muted" style="font-size:10px; font-weight:700; text-transform:uppercase;">Telemetry Timestamp</span>'
            f'<div style="font-size: 13px; font-weight: 600; color: {c["text_subtle"]}; margin-top: 2px;">{format_timestamp(timestamp)}</div>'
            f'</div>'
            f'</div>'
            f'</div>'
        )
        st.markdown(class_html, unsafe_allow_html=True)

    with col_meta:
        metrics_html = (
            f'<div class="status-card" style="box-shadow: 0 4px 16px rgba(0,0,0,0.12);">'
            f'<div style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase; margin-bottom: 10px;">'
            f'Backend Workload Metrics Payload'
            f'</div>'
        )
        if raw_metrics:
            metrics_html += (
                f'<pre style="background:{c["card_bg_elevated"]}; border:1px solid {c["card_border"]}; padding:10px; border-radius:6px; font-size:11px; color:{c["text"]}; max-height:160px; overflow-y:auto;">'
                f'{str(raw_metrics)}'
                f'</pre>'
            )
        else:
            metrics_html += (
                f'<div style="background:{c["card_bg_elevated"]}; border:1px solid {c["card_border"]}; padding:12px; border-radius:6px;">'
                f'<div style="font-size:12px; color:{c["text_subtle"]};">'
                f'<code>metrics: null</code><br><br>'
                f'The backend telemetry payload contains no secondary metric dictionary for this window. '
                f'Additional skew and concurrency indices will render here automatically when exposed.'
                f'</div>'
                f'</div>'
            )
        metrics_html += (
            f'<div style="margin-top: 14px; font-size: 11px; color: {c["text_subtle"]};">'
            f'Endpoint: <code>GET /telemetry/workload</code> &bull; Polling: Real-time'
            f'</div>'
            f'</div>'
        )
        st.markdown(metrics_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # CURRENT WINDOW ACCESS PATTERNS
    # --------------------------------------------------
    st.markdown(
        f"""<div style="margin: 28px 0 10px 0;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                Observed Window Access Counts & Key Velocity
            </h3>
            <p style="margin: 4px 0 0 0; font-size: 12.5px; color: {c['text_muted']};">
                Active access frequency observed across current and previous sliding telemetry windows.
            </p>
        </div>""",
        unsafe_allow_html=True,
    )

    curr_counts = obs.get("current_window_access_counts", {})
    prev_counts = obs.get("previous_window_access_counts", {})

    all_keys = set(list(curr_counts.keys()) + list(prev_counts.keys()))

    if all_keys:
        table_rows = []
        for k in sorted(all_keys):
            c_cnt = curr_counts.get(k, 0)
            p_cnt = prev_counts.get(k, 0)
            velocity = c_cnt - p_cnt
            table_rows.append({
                "Key Identifier": k,
                "Current Window Accesses": c_cnt,
                "Previous Window Accesses": p_cnt,
                "Velocity Delta": f"{'+' if velocity > 0 else ''}{velocity}",
            })
        df_access = pd.DataFrame(table_rows)
        st.dataframe(df_access, use_container_width=True, hide_index=True)
    else:
        st.markdown(
            f"""
            <div class="hero-card" style="text-align: center; padding: 28px 16px;">
                <div style="font-size: 24px; margin-bottom: 6px;">📥</div>
                <div style="font-weight: 700; font-size: 13.5px; color: {c['text']}; margin-bottom: 4px;">
                    No Active Access Keys Recorded Yet
                </div>
                <div style="font-size: 12px; color: {c['text_muted']}; max-width: 420px; margin: 0 auto 12px auto;">
                    Run requests in the <strong>Request Simulator</strong> to observe live access counts dynamically populate here.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
