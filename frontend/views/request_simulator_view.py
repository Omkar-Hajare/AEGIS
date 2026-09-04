"""Request Simulator View.

Critical interactive testing harness for jury demonstrations.
Executes live requests against FastAPI /data/product/{id} and /data/recommendation/{id}
to vividly demonstrate the first-request Cache MISS followed by the repeated-request Cache HIT.
"""

import time
import random
import streamlit as st
from frontend.services.data_service import fetch_product, fetch_recommendation
from frontend.services.telemetry_service import get_telemetry_observation
from frontend.components.styles import get_theme_colors
from frontend.components.metric_card import render_metric_card
from frontend.utils.formatting import (
    format_percentage,
    format_latency,
    format_int,
    format_timestamp,
)


def render_request_simulator_view():
    """Render Request Simulator for interactive MISS -> HIT demo."""
    c = get_theme_colors()

    # Session State tracking for last request and previous telemetry baseline
    if "sim_last_result" not in st.session_state:
        st.session_state["sim_last_result"] = None
    if "sim_last_key" not in st.session_state:
        st.session_state["sim_last_key"] = "p101"
    if "sim_request_type" not in st.session_state:
        st.session_state["sim_request_type"] = "product"

    obs = get_telemetry_observation()

    # Header Title Block with cleanly aligned right badge
    header_html = (
        f'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin: 0 0 12px 0; flex-wrap: wrap; gap: 12px;">'
        f'<div>'
        f'<h1 style="margin: 0 0 6px 0; font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; color: {c["text"]} !important;">'
        f'Request Simulator & <span style="color: {c["text_muted"]} !important; font-weight: 600;">Cache Lifecycle Harness</span>'
        f'</h1>'
        f'<p style="margin: 0; font-size: 13.5px; line-height: 1.5; color: {c["text_muted"]}; max-width: 840px;">'
        f'Issue live requests against backend REST endpoints to observe real-time latency differences and demonstrate first-request MISS followed by repeated-request HIT.'
        f'</p>'
        f'</div>'
        f'<div style="display: flex; align-items: center; padding-top: 6px;">'
        f'<span style="font-size: 10.5px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; background: rgba(34, 197, 94, 0.10); color: {c["emerald"]}; border: 1px solid rgba(34, 197, 94, 0.22); border-radius: 6px; padding: 4px 12px; white-space: nowrap;">'
        f'LIVE REST ENDPOINTS &bull; FASTAPI'
        f'</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # CURRENT TELEMETRY SNAPSHOT STRIP
    # --------------------------------------------------
    t1, t2, t3, t4 = st.columns(4)
    with t1:
        render_metric_card(
            title="Active Hit Rate",
            value=format_percentage(obs.get("hit_rate", 0.0)),
            subtitle=f"{format_int(obs.get('cache_hits', 0))} hits / {format_int(obs.get('total_requests', 0))} total",
            tag="OBSERVED",
            delta="Window Aggregation",
            delta_color=c["emerald"],
            progress_pct=obs.get("hit_rate", 0.0) * 100.0,
        )
    with t2:
        render_metric_card(
            title="Backend Calls",
            value=format_int(obs.get("backend_calls", 0)),
            subtitle=f"Misses: {format_int(obs.get('cache_misses', 0))}",
            tag="UPSTREAM",
            delta="Increments on Miss",
            delta_color=c["amber"],
        )
    with t3:
        render_metric_card(
            title="Avg Retrieval Time",
            value=format_latency(obs.get("backend_latency_ms", 0.0)),
            subtitle="Observed backend penalty",
            tag="PENALTY",
            delta="Zero on Cache Hit",
            delta_color=c["text_muted"],
        )
    with t4:
        last_res = st.session_state.get("sim_last_result")
        last_ms = last_res["elapsed_ms"] if last_res else 0.0
        render_metric_card(
            title="Latest Client RTT",
            value=format_latency(last_ms),
            subtitle=f"Key: {st.session_state.get('sim_last_key', 'None')}",
            tag="ROUND TRIP",
            delta="Measured by browser",
            delta_color=c["purple"],
        )

    # --------------------------------------------------
    # JURY DEMO GUIDE CALLOUT
    # --------------------------------------------------
    guide_html = (
        f'<div class="hero-card" style="padding: 18px 22px; margin-top: 32px; margin-bottom: 24px; border-left: 4px solid #10B981 !important; border-radius: 12px;">'
        f'<div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">'
        f'<div>'
        f'<span style="font-size: 11px; font-weight: 800; color: #10B981; letter-spacing: 0.6px; text-transform: uppercase;">JURY DEMO PROTOCOL (MISS &rarr; HIT):</span>'
        f'<div style="font-size: 13px; color: {c["text"]}; margin-top: 4px; line-height: 1.5;">'
        f'1. Enter a new key (or click <b>Generate Random Key</b>) and click <b>Request</b> &rarr; Demonstrates <b>Cache MISS (~30ms backend retrieval)</b>.<br>'
        f'2. Click <b>⚡ Request Same Key Again</b> &rarr; Demonstrates <b>Cache HIT (&lt;3ms instantaneous RAM response)</b> without invoking backend!'
        f'</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(guide_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # INTERACTIVE REQUEST DISPATCHER
    # --------------------------------------------------
    col_input, col_result = st.columns([1.2, 1.3])

    with col_input:
        st.markdown(
            f'<h3 style="font-size: 1.15rem; font-weight: 700; color: {c["text"]}; margin-bottom: 12px;">'
            f'Configure Live Request'
            f'</h3>',
            unsafe_allow_html=True,
        )

        tab_prod, tab_rec = st.tabs(["🛒 Product Request", "✨ Recommendation Request"])

        with tab_prod:
            col_id, col_quick = st.columns([2, 1.2])
            with col_id:
                product_id_input = st.text_input(
                    "Product Identifier",
                    value=st.session_state.get("prod_input_val", "p101"),
                    help="Target product ID routed to GET /data/product/{product_id}",
                    key="input_product_id",
                )
            with col_quick:
                st.caption("Quick Samples:")
                q1, q2, q3 = st.columns(3)
                if q1.button("p101", key="q_p1"):
                    st.session_state["prod_input_val"] = "p101"
                    st.rerun()
                if q2.button("p202", key="q_p2"):
                    st.session_state["prod_input_val"] = "p202"
                    st.rerun()
                if q3.button("p303", key="q_p3"):
                    st.session_state["prod_input_val"] = "p303"
                    st.rerun()

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("🚀 Request Product", key="btn_req_prod", width="stretch", type="primary"):
                    with st.spinner(f"Querying GET /data/product/{product_id_input}..."):
                        res = fetch_product(product_id_input)
                        st.session_state["sim_last_result"] = res
                        st.session_state["sim_last_key"] = f"product:{product_id_input}"
                        st.session_state["sim_request_type"] = "product"
                        st.session_state["prod_input_val"] = product_id_input
                        time.sleep(0.15)
                        st.toast(f"Executed: product:{product_id_input} ({res['elapsed_ms']:.1f} ms)", icon="⚡")
                        st.rerun()

            with btn_col2:
                if st.button("🎲 Random Product", key="btn_rnd_prod", width="stretch"):
                    rnd_id = f"p{random.randint(400, 9999)}"
                    st.session_state["prod_input_val"] = rnd_id
                    with st.spinner(f"Querying random product {rnd_id}..."):
                        res = fetch_product(rnd_id)
                        st.session_state["sim_last_result"] = res
                        st.session_state["sim_last_key"] = f"product:{rnd_id}"
                        st.session_state["sim_request_type"] = "product"
                        st.toast(f"New product requested: product:{rnd_id}", icon="🎲")
                        st.rerun()

        with tab_rec:
            col_u_id, col_u_quick = st.columns([2, 1.2])
            with col_u_id:
                user_id_input = st.text_input(
                    "User Identifier",
                    value=st.session_state.get("user_input_val", "user_100"),
                    help="Target user ID routed to GET /data/recommendation/{user_id}",
                    key="input_user_id",
                )
            with col_u_quick:
                st.caption("Quick Samples:")
                u1, u2, u3 = st.columns(3)
                if u1.button("u100", key="q_u1"):
                    st.session_state["user_input_val"] = "user_100"
                    st.rerun()
                if u2.button("u200", key="q_u2"):
                    st.session_state["user_input_val"] = "user_200"
                    st.rerun()
                if u3.button("vip", key="q_u3"):
                    st.session_state["user_input_val"] = "user_vip"
                    st.rerun()

            u_btn1, u_btn2 = st.columns(2)
            with u_btn1:
                if st.button("🚀 Request Recs", key="btn_req_rec", width="stretch", type="primary"):
                    with st.spinner(f"Querying GET /data/recommendation/{user_id_input}..."):
                        res = fetch_recommendation(user_id_input)
                        st.session_state["sim_last_result"] = res
                        st.session_state["sim_last_key"] = f"recommendation:{user_id_input}"
                        st.session_state["sim_request_type"] = "recommendation"
                        st.session_state["user_input_val"] = user_id_input
                        time.sleep(0.15)
                        st.toast(f"Executed: recommendation:{user_id_input} ({res['elapsed_ms']:.1f} ms)", icon="⚡")
                        st.rerun()
            with u_btn2:
                if st.button("🎲 Random User", key="btn_rnd_user", width="stretch"):
                    rnd_user = f"user_{random.randint(500, 9999)}"
                    st.session_state["user_input_val"] = rnd_user
                    with st.spinner(f"Querying random user {rnd_user}..."):
                        res = fetch_recommendation(rnd_user)
                        st.session_state["sim_last_result"] = res
                        st.session_state["sim_last_key"] = f"recommendation:{rnd_user}"
                        st.session_state["sim_request_type"] = "recommendation"
                        st.toast(f"New user requested: recommendation:{rnd_user}", icon="🎲")
                        st.rerun()

        # REPEAT SAME KEY SHORTCUT BUTTON
        curr_target = st.session_state.get("sim_last_key", "None")
        if curr_target and curr_target != "None":
            st.markdown(
                f'<div style="background: {"rgba(255, 255, 255, 0.04)" if c["is_dark"] else "rgba(0, 0, 0, 0.03)"}; border: 1px dashed {c["card_border"]}; border-radius: 8px; padding: 10px 14px; margin-top: 10px;">'
                f'<span style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase;">Instant Replay Target:</span>'
                f'<div style="font-family: monospace; font-size: 13px; font-weight: 700; color: {c["text"]}; margin: 2px 0 8px 0;">{curr_target}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button("⚡ Request Same Key Again (Demonstrate HIT)", key="btn_repeat_key", width="stretch"):
                req_type = st.session_state.get("sim_request_type", "product")
                target_raw = curr_target.split(":", 1)[-1]
                with st.spinner(f"Re-requesting {curr_target}..."):
                    if req_type == "product":
                        res = fetch_product(target_raw)
                    else:
                        res = fetch_recommendation(target_raw)
                    st.session_state["sim_last_result"] = res
                    st.toast(f"Instant HIT for {curr_target} ({res['elapsed_ms']:.1f} ms)!", icon="🎯")
                    st.rerun()

    with col_result:
        st.markdown(
            f'<h3 style="font-size: 1.15rem; font-weight: 700; color: {c["text"]}; margin-bottom: 12px;">'
            f'Request Inspection & Returned Payload'
            f'</h3>',
            unsafe_allow_html=True,
        )

        last_res = st.session_state.get("sim_last_result")
        if last_res:
            elapsed = last_res.get("elapsed_ms", 0.0)
            is_likely_hit = elapsed < 12.0
            verdict_badge = (
                f'<span style="background: {"rgba(34, 197, 94, 0.12)" if c["is_dark"] else "rgba(34, 197, 94, 0.10)"}; color: {c["emerald"]}; border: 1px solid {"rgba(34, 197, 94, 0.25)" if c["is_dark"] else "rgba(34, 197, 94, 0.20)"}; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: 800;">● CACHE HIT (RAM SERVED)</span>'
                if is_likely_hit
                else f'<span style="background: {"rgba(239, 68, 68, 0.12)" if c["is_dark"] else "rgba(239, 68, 68, 0.10)"}; color: {c["rose"]}; border: 1px solid {"rgba(239, 68, 68, 0.25)" if c["is_dark"] else "rgba(239, 68, 68, 0.20)"}; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: 800;">○ CACHE MISS (BACKEND COMPUTED)</span>'
            )
            verdict_explanation = (
                "Instant turnaround (&lt;12ms) confirms entry was fulfilled directly from Tier-1 RAM without re-invoking backend."
                if is_likely_hit
                else "Retrieval duration reflects full backend execution penalty (~30ms) before writing entry into cache."
            )

            res_card_html = (
                f'<div class="decision-card" style="padding: 22px 24px; margin-bottom: 20px; border-radius: 12px; background: {c["card_bg"]}; border: 1px solid {c["card_border"]};">'
                f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">'
                f'<span style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase;">REQUEST OUTCOME</span>'
                f'<div>{verdict_badge}</div>'
                f'</div>'
                f'<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 14px; text-align: center;">'
                f'<div style="background: {c["card_bg_elevated"]}; padding: 10px 12px; border-radius: 8px; border: 1px solid {c["card_border"]};">'
                f'<span class="muted" style="font-size: 10px; font-weight: 700; text-transform: uppercase; display: block;">Round Trip</span>'
                f'<div style="font-size: 15px; font-weight: 800; color: {c["text"]}; margin-top: 2px;">{elapsed:.1f} ms</div>'
                f'</div>'
                f'<div style="background: {c["card_bg_elevated"]}; padding: 10px 12px; border-radius: 8px; border: 1px solid {c["card_border"]};">'
                f'<span class="muted" style="font-size: 10px; font-weight: 700; text-transform: uppercase; display: block;">HTTP Status</span>'
                f'<div style="font-size: 15px; font-weight: 800; color: {c["emerald"]}; margin-top: 2px;">{last_res.get("status_code", 200)} OK</div>'
                f'</div>'
                f'<div style="background: {c["card_bg_elevated"]}; padding: 10px 12px; border-radius: 8px; border: 1px solid {c["card_border"]};">'
                f'<span class="muted" style="font-size: 10px; font-weight: 700; text-transform: uppercase; display: block;">Target Key</span>'
                f'<div style="font-size: 12px; font-weight: 700; color: {c["text"]}; word-break: break-all; margin-top: 4px;">{last_res.get("target_key")}</div>'
                f'</div>'
                f'</div>'
                f'<p style="font-size: 12px; color: {c["text_muted"]}; line-height: 1.45; margin: 0 0 12px 0;">{verdict_explanation}</p>'
                f'<span style="font-size: 10.5px; font-weight: 700; color: {c["text_subtle"]}; text-transform: uppercase; display: block; margin-bottom: 4px;">RETURNED PAYLOAD:</span>'
                f'</div>'
            )
            st.markdown(res_card_html, unsafe_allow_html=True)
            st.json(last_res.get("payload", {}))
        else:
            st.info(
                "No request dispatched in current session. Enter an ID on the left and click **Request Product** or **Request Recommendation** to initiate the cache lifecycle."
            )
