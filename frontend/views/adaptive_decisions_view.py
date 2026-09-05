import pandas as pd
import streamlit as st

from frontend.components.metric_card import render_metric_card
from frontend.components.styles import get_theme_colors
from frontend.mocks import data as mock_data
from frontend.services.api_client import (
    get_cache_objects,
    get_decision_history,
    get_runtime_decision,
)
from frontend.services.telemetry_service import (
    get_system_state,
    get_telemetry_observation,
)
from frontend.utils.formatting import (
    format_bytes,
    format_latency,
    format_percentage,
    format_request_rate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _action_color(c: dict, action: str) -> str:
    action = (action or "").upper()
    if action in ("SCALE_UP", "GROW"):
        return c["emerald"]
    if action in ("SCALE_DOWN", "SHRINK"):
        return c["rose"]
    if action == "MAINTAIN":
        return c["text_muted"]
    return c["purple"]


def _bytes_to_mb(b) -> str:
    if b is None:
        return "—"
    try:
        return f"{int(b) / (1024 * 1024):.1f} MB"
    except (TypeError, ValueError):
        return str(b)


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

def render_adaptive_decisions_view():
    """Render Adaptive Decisions & Arbitration Engine with live backend decision + sensitivity tuner."""
    c = get_theme_colors()

    # ------------------------------------------------------------------ live telemetry
    obs = get_telemetry_observation()
    sys_state = get_system_state()
    is_obs_live = obs.get("is_live", False)

    # ------------------------------------------------------------------ live adaptive decision
    live_decision = get_runtime_decision()
    decision_is_live = live_decision is not None

    mock_decision = mock_data.adaptive_decision

    if decision_is_live:
        decision = live_decision
        capacity_action = decision.get("capacity_action", "MAINTAIN")
        recommended_bytes = decision.get("recommended_capacity_bytes")
        eviction_keys = decision.get("eviction_keys", [])
        reason = decision.get("reason", "")
        decision_id = decision.get("decision_id", "")
        decision_ts = decision.get("timestamp", "")
        object_scores = decision.get("object_scores", {})
        metadata = decision.get("metadata", {})
    else:
        decision = mock_decision
        capacity_action = decision.get("capacity_action", decision.get("action", "SCALE_UP"))
        recommended_bytes = decision.get("recommended_capacity_bytes")
        eviction_keys = decision.get("eviction_keys", [])
        reason = decision.get("reason", "")
        decision_id = decision.get("eval_cycle_id", "—")
        decision_ts = decision.get("timestamp", "—")
        object_scores = {}
        metadata = {}

    # Cache objects schema (DEMO only)
    objects = get_cache_objects()

    # ==================================================================
    # HEADER
    # ==================================================================
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

    # ==================================================================
    # LIVE/DEMO BAND
    # ==================================================================
    live_color = c["emerald"] if decision_is_live else c["amber"]
    live_label = "⚡ LIVE — GET /adaptive/runtime-decision" if decision_is_live else "⚠️ DEMO FALLBACK — backend offline"
    band_html = (
        f'<div class="hero-card" style="padding: 12px 18px; margin-bottom: 20px; border: 1px solid {c["card_border"]} !important; border-left: 3px solid {live_color} !important;">'
        f'<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">'
        f'<strong style="font-size: 13px; color: {c["text"]};">Adaptive Engine Decision</strong>'
        f'<span style="font-size: 10px; font-weight: 800; color: {live_color}; background: {"rgba(34,197,94,0.10)" if decision_is_live else "rgba(245,158,11,0.10)"}; border: 1px solid {"rgba(34,197,94,0.25)" if decision_is_live else "rgba(245,158,11,0.25)"}; border-radius: 4px; padding: 2px 8px;">{live_label}</span>'
        f'</div>'
        f'<p style="font-size: 12px; color: {c["text_muted"]}; margin: 0; line-height: 1.5;">'
        + (f'Decision ID: <code>{decision_id}</code> &bull; ' if decision_id else '')
        + (f'Timestamp: <code>{decision_ts}</code>' if decision_ts else '')
        + '</p>'
        '</div>'
    )
    st.markdown(band_html, unsafe_allow_html=True)

    # ==================================================================
    # TELEMETRY SIGNAL STRIP
    # ==================================================================
    live_signals_label = "LIVE" if is_obs_live else "DEMO"
    st.markdown(
        f"""<div style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
            <h4 style="margin: 0; font-size: 1rem; font-weight: 700; color: {c['text']};">
                Active Telemetry Signals Feeding Arbiter
            </h4>
            <span style="font-size: 11px; color: {c['text_muted']}; font-weight: 600;">{live_signals_label} INPUT VECTORS</span>
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

    # ==================================================================
    # DECISION KPI STRIP
    # ==================================================================
    action_col = _action_color(c, capacity_action)
    recommended_mb_str = _bytes_to_mb(recommended_bytes)
    eviction_count = len(eviction_keys)

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
            capacity_action,
            subtitle="Evaluated by DecisionEngine",
            tag="LIVE ACTION" if decision_is_live else "DEMO ACTION",
            delta="Current capacity verdict",
            delta_color=action_col,
            tooltip="Capacity action dispatched by the adaptive engine for this decision cycle.",
            progress_value=0.85,
            progress_color=action_col,
        )
    with m3:
        render_metric_card(
            "Recommended Capacity",
            recommended_mb_str,
            subtitle="Engine recommended allocation",
            tag="LIVE" if decision_is_live else "DEMO",
            delta="+Elastic Scaling" if capacity_action in ("SCALE_UP", "GROW") else "Stable",
            delta_color=c["text_muted"],
            tooltip="Recommended memory tier to maintain target hit-rate under current workload.",
            progress_value=0.75,
            progress_color=c["text_muted"],
        )
    with m4:
        render_metric_card(
            "Eviction Candidates",
            f"{eviction_count} Keys",
            subtitle="Flagged by engine this cycle",
            tag="LIVE" if decision_is_live else "DEMO",
            delta="Low utility density",
            delta_color=c["rose"] if eviction_count > 0 else c["emerald"],
            is_floating=True,
            tooltip="Number of cache keys the engine recommends evicting in this decision cycle.",
            progress_value=min(1.0, eviction_count / 5.0),
            progress_color=c["rose"],
        )

    # ==================================================================
    # ACTIVE DECISION DETAIL CARD
    # ==================================================================
    st.markdown(
        f"""<div style="margin: 28px 0 10px 0; display: flex; align-items: center; justify-content: space-between;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                Active Arbiter Cycle Output
            </h3>
            <span style="font-size: 11px; font-weight: 700; color: {c['emerald'] if decision_is_live else c['amber']};">
                {"⚡ LIVE BACKEND" if decision_is_live else "⚠️ DEMO FALLBACK"}
            </span>
        </div>""",
        unsafe_allow_html=True,
    )

    card_html = (
        f'<div class="decision-card" style="padding: 22px 24px; margin-bottom: 20px; border-radius: 12px; background: {c["card_bg"]}; border: 1px solid {c["card_border"]};">'
        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">'
        f'<span style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase;">ENGINE VERDICT</span>'
        f'<span style="font-size: 12px; font-weight: 800; color: {action_col}; padding: 3px 10px; border-radius: 5px; border: 1px solid {action_col};">{capacity_action}</span>'
        f'</div>'
    )
    if reason:
        card_html += (
            f'<div style="margin-bottom: 14px; padding: 10px 14px; background: {c["card_bg_elevated"]}; border-radius: 8px; border: 1px solid {c["card_border"]};">'
            f'<span style="font-size: 10px; font-weight: 800; color: {c["text_muted"]}; text-transform: uppercase;">REASON</span>'
            f'<div style="font-size: 12.5px; color: {c["text"]}; margin-top: 4px; line-height: 1.5;">{reason}</div>'
            f'</div>'
        )
    if eviction_keys:
        keys_str = " &bull; ".join(f"<code>{k}</code>" for k in eviction_keys[:6])
        if len(eviction_keys) > 6:
            keys_str += f' <span style="color:{c["text_muted"]};">+{len(eviction_keys) - 6} more</span>'
        card_html += (
            f'<div style="margin-bottom: 14px;">'
            f'<span style="font-size: 10px; font-weight: 800; color: {c["rose"]}; text-transform: uppercase; display: block; margin-bottom: 4px;">EVICTION CANDIDATES</span>'
            f'<div style="font-size: 12px; color: {c["text"]}; line-height: 1.7;">{keys_str}</div>'
            f'</div>'
        )
    if recommended_bytes:
        card_html += (
            f'<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; text-align: center;">'
            f'<div style="background: {c["card_bg_elevated"]}; padding: 10px 8px; border-radius: 8px; border: 1px solid {c["card_border"]};">'
            f'<span class="muted" style="font-size: 9.5px; font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 2px;">Recommended</span>'
            f'<div style="font-size: 15px; font-weight: 800; color: {c["emerald"]};">{recommended_mb_str}</div>'
            f'</div>'
            f'<div style="background: {c["card_bg_elevated"]}; padding: 10px 8px; border-radius: 8px; border: 1px solid {c["card_border"]};">'
            f'<span class="muted" style="font-size: 9.5px; font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 2px;">Action</span>'
            f'<div style="font-size: 15px; font-weight: 800; color: {action_col};">{capacity_action}</div>'
            f'</div>'
            f'</div>'
        )
    card_html += '</div>'
    st.markdown(card_html, unsafe_allow_html=True)

    # ==================================================================
    # OBJECT SCORES TABLE (live only)
    # ==================================================================
    if decision_is_live and object_scores:
        st.markdown(
            f"""<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <h4 style="margin: 0; font-size: 1rem; font-weight: 700; color: {c['text']};">
                    Per-Object Utility Scores (Live Engine Output)
                </h4>
                <span style="font-size: 11px; color: {c['emerald']}; font-weight: 700;">⚡ LIVE BACKEND</span>
            </div>""",
            unsafe_allow_html=True,
        )
        score_rows = [
            {"Cache Key": k, "Utility Score": round(float(v), 4)}
            for k, v in sorted(object_scores.items(), key=lambda x: x[1], reverse=True)
        ]
        st.dataframe(
            pd.DataFrame(score_rows),
            column_config={
                "Cache Key": st.column_config.TextColumn("Cache Key", width="large"),
                "Utility Score": st.column_config.ProgressColumn(
                    "Utility Score", min_value=0.0, max_value=1.0, format="%.4f"
                ),
            },
            hide_index=True,
            width="stretch",
        )

    # Decision metadata expander (live only)
    if decision_is_live and metadata:
        with st.expander("Decision Metadata (raw)", expanded=False):
            st.json(metadata)

    st.markdown(
        f'<div style="height: 1px; background: {c["card_border"]}; margin: 20px 0;"></div>',
        unsafe_allow_html=True,
    )

    # ==================================================================
    # MULTI-FACTOR WEIGHT SENSITIVITY TUNER (DEMO schema data)
    # ==================================================================
    st.markdown(
        f"""<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                Multi-Factor Signal Sensitivity Tuner
            </h3>
            <span class="badge-pill badge-active">GDSF PARAMETER ENGINE &bull; SCHEMA DEMO</span>
        </div>""",
        unsafe_allow_html=True,
    )
    st.caption(
        "Interactively adjust the weights of the multi-factor scoring function: Score = (Cost^α × Latency^β × Frequency) / (Size^γ × StalePenalty). "
        "Object data below comes from schema demo (no live object-listing endpoint)."
    )

    t1, t2, t3 = st.columns(3)
    with t1:
        alpha = st.slider(
            "Recompute Cost Weight (α)",
            min_value=0.0, max_value=3.0, value=1.2, step=0.1,
            help="Higher α aggressively protects expensive 3rd-party API calls (e.g. OpenAI/Anthropic inference).",
        )
    with t2:
        beta = st.slider(
            "Miss Latency Weight (β)",
            min_value=0.0, max_value=3.0, value=1.0, step=0.1,
            help="Higher β prioritizes slow database read queries over lightweight microservice lookups.",
        )
    with t3:
        gamma = st.slider(
            "Object Size Penalty (γ)",
            min_value=0.1, max_value=2.0, value=0.8, step=0.1,
            help="Higher γ penalizes bulky assets to free up RAM capacity for high-density key entries.",
        )

    recomputed_rows = []
    for obj in objects:
        c_val = obj.get("recompute_cost_usd", 0.01)
        l_val = obj.get("retrieval_cost_ms", 10.0)
        s_val = max(obj.get("size_kb", 1.0), 0.1)
        f_val = obj.get("access_count", 10)

        raw = (c_val ** alpha) * (l_val ** beta) * f_val / (s_val ** gamma)
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
        f"#### Recomputed Arbitration Rankings with α={alpha:.1f}, β={beta:.1f}, γ={gamma:.1f} &nbsp;"
        f'<span style="font-size: 11px; font-weight: 700; color: {c["amber"]};">[DEMO — schema objects]</span>',
        unsafe_allow_html=True,
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

    # ==================================================================
    # DECISION AUDIT LOG TABLE (LIVE / OFFLINE FALLBACK)
    # ==================================================================
    history_response = get_decision_history()
    history_is_live = history_response.get("is_live", False)
    history_decisions = history_response.get("decisions", [])

    if history_is_live:
        audit_badge_color = c["emerald"]
        audit_badge_text = f"⚡ LIVE — GET /adaptive/decisions ({len(history_decisions)} recorded)"
    else:
        audit_badge_color = c["amber"]
        audit_badge_text = "⚠️ DEMO FALLBACK — backend offline"

    st.markdown(
        f"""<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                Decision Audit Log
            </h3>
            <span style="font-size: 11px; font-weight: 700; color: {audit_badge_color};">{audit_badge_text}</span>
        </div>""",
        unsafe_allow_html=True,
    )

    if history_is_live:
        audit_records = []
        for dec in history_decisions:
            ts = dec.get("timestamp", "")
            if isinstance(ts, str) and "T" in ts:
                time_str = ts.split("T")[1][:8]
            else:
                time_str = str(ts)[:8] if ts else "—"

            cid = dec.get("decision_id") or "DEC-LIVE"
            cap_act = str(dec.get("capacity_action", "MAINTAIN")).upper()
            evictions = dec.get("eviction_keys", [])
            scores = dec.get("object_scores", {})
            reason_str = dec.get("reason", "")
            rec_bytes = dec.get("recommended_capacity_bytes")

            if evictions:
                act = "EVICT"
                target = ", ".join(evictions[:2]) + (f" (+{len(evictions)-2})" if len(evictions) > 2 else "")
                score_val = f"{min(scores.values()):.2f}" if scores else "—"
                footprint = "Eviction Target"
            else:
                act = cap_act
                target = "SYSTEM_RAM_TIER" if "SCALE" in act else (next(iter(scores.keys())) if scores else "CACHE_METRICS")
                score_val = f"{max(scores.values()):.2f}" if scores else "N/A"
                footprint = f"{_bytes_to_mb(rec_bytes)} Target" if rec_bytes else "Stable"

            audit_records.append(
                {
                    "Timestamp": time_str,
                    "Cycle ID": cid,
                    "Target Key": target,
                    "Action": act,
                    "Utility Score": score_val,
                    "Memory Freed": footprint,
                    "Cost Impact": reason_str[:70] + ("..." if len(reason_str) > 70 else ""),
                    "Status": "Recorded",
                }
            )
    else:
        # Offline fallback mock data
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

    df_audit = pd.DataFrame(audit_records)

    if history_is_live and df_audit.empty:
        st.info("No runtime decisions recorded yet in memory. Run requests through the Request Simulator or invoke GET /adaptive/runtime-decision to produce live audit logs.")
    else:
        filter_options = ["ALL"]
        if not df_audit.empty and "Action" in df_audit.columns:
            present_actions = sorted(df_audit["Action"].unique())
            filter_options = ["ALL"] + [a for a in present_actions if a != "ALL"]

        action_filter = st.radio(
            "Filter Audit Records",
            filter_options,
            horizontal=True,
            label_visibility="collapsed",
        )

        if action_filter != "ALL" and not df_audit.empty:
            df_audit = df_audit[df_audit["Action"] == action_filter]

        st.dataframe(
            df_audit,
            column_config={
                "Timestamp": st.column_config.TextColumn("Timestamp", width="small"),
                "Cycle ID": st.column_config.TextColumn("Cycle ID", width="small"),
                "Target Key": st.column_config.TextColumn("Target Key", width="medium"),
                "Action": st.column_config.TextColumn("Verdict", width="small"),
                "Utility Score": st.column_config.TextColumn("Score", width="small"),
                "Memory Freed": st.column_config.TextColumn("Footprint Delta", width="small"),
                "Cost Impact": st.column_config.TextColumn("Cost Avoidance / Impact", width="large"),
                "Status": st.column_config.TextColumn("Status", width="small"),
            },
            width="stretch",
            hide_index=True,
        )
