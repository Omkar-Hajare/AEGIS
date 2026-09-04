"""Cost Analysis View.

Evaluates cost-aware caching efficiency using measured backend retrieval latency
and compute offload signals, while honestly indicating that monetary cost model endpoints
are pending backend integration.
"""

import streamlit as st
from frontend.services.telemetry_service import get_telemetry_observation
from frontend.components.styles import get_theme_colors
from frontend.components.metric_card import render_metric_card
from frontend.utils.formatting import (
    format_latency,
    format_int,
    format_duration,
)


def render_cost_analysis_view():
    """Render Cost Analysis and Economic Value Density framework."""
    c = get_theme_colors()
    obs = get_telemetry_observation()

    total_reqs = obs.get("total_requests", 0)
    hits = obs.get("cache_hits", 0)
    backend_calls = obs.get("backend_calls", 0)
    latency_ms = obs.get("backend_latency_ms", 0.0)

    # Derived time saved = hits * latency_ms
    time_saved_s = (hits * latency_ms) / 1000.0

    # Header Title Block with cleanly aligned right badge
    header_html = (
        f'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin: 8px 0 22px 0; flex-wrap: wrap; gap: 12px;">'
        f'<div>'
        f'<h1 style="margin: 0 0 6px 0; font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; color: {c["text"]} !important;">'
        f'Cost Analysis & <span style="color: {c["cyan"]} !important;">Economic Value Density</span>'
        f'</h1>'
        f'<p style="margin: 0; font-size: 13.5px; line-height: 1.5; color: {c["text_muted"]}; max-width: 840px;">'
        f'Evaluate cache economics through measured backend retrieval latency and compute offload, grounding decisions in cost-to-recompute metrics.'
        f'</p>'
        f'</div>'
        f'<div style="display: flex; align-items: center; padding-top: 6px;">'
        f'<span style="font-size: 10.5px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; background: rgba(245, 158, 11, 0.12); color: {c["amber"]}; border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 6px; padding: 4px 12px; white-space: nowrap;">'
        f'COST MODEL &bull; CONTRACT INTEGRATION'
        f'</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # HONEST CONTRACT INTEGRATION NOTICE
    # --------------------------------------------------
    notice_html = (
        f'<div class="hero-card" style="padding: 14px 18px; margin-bottom: 20px; border-left: 4px solid {c["amber"]} !important;">'
        f'<div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">'
        f'<div>'
        f'<span style="font-size: 11px; font-weight: 800; color: {c["amber"]}; letter-spacing: 0.6px; text-transform: uppercase;">BACKEND CONTRACT STATUS:</span>'
        f'<div style="font-size: 12.5px; color: {c["text"]}; margin-top: 2px;">'
        f'Monetary dollar pricing API not currently exposed by backend. Displaying strictly <b>[MEASURED]</b> latency signals and compute offload to avoid fabricating unverified savings.'
        f'</div>'
        f'</div>'
        f'<span style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; background: rgba(255,255,255,0.05); padding: 3px 8px; border-radius: 4px;">NO FABRICATED CURRENCY</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(notice_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # MEASURED VS DERIVED SIGNALS STRIP
    # --------------------------------------------------
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        render_metric_card(
            title="Backend Latency",
            value=format_latency(latency_ms),
            subtitle="Observed retrieval cost",
            tag="[MEASURED]",
            delta="Incurred per miss",
            delta_color=c["amber"],
            tooltip="Live measured time to fetch data from backend database/microservices on a cache miss.",
        )

    with m2:
        render_metric_card(
            title="Compute Offload",
            value=f"{format_int(hits)} Reqs",
            subtitle=f"Of {format_int(total_reqs)} total requests",
            tag="[MEASURED]",
            delta="Zero Upstream Load",
            delta_color=c["emerald"],
            tooltip="Number of client requests completely served from cache without invoking backend compute.",
        )

    with m3:
        render_metric_card(
            title="Cumulative Time Saved",
            value=f"{time_saved_s:.2f}s",
            subtitle=f"{hits} hits &times; {latency_ms:.1f}ms",
            tag="[DERIVED]",
            delta="Aggregated latency saved",
            delta_color=c["cyan"],
            tooltip="Derived metric: total seconds of backend latency avoided by cache hits in this window.",
        )

    with m4:
        render_metric_card(
            title="Economic Value Density",
            value="Ready for API",
            subtitle="Formula: (Cost &times; Freq) / Size",
            tag="[PROJECTED]",
            delta="Pending Cost Endpoint",
            delta_color=c["purple"],
            tooltip="Theoretical metric calculated by Person 1's adaptive engine to prioritize high-cost objects.",
        )

    st.write("")

    # --------------------------------------------------
    # ECONOMIC VALUE FORMULATION & COMPONENT ARCHITECTURE
    # --------------------------------------------------
    col_formula, col_signals = st.columns([1.2, 1.2])

    with col_formula:
        st.markdown(
            f'<h3 style="font-size: 1.15rem; font-weight: 700; color: {c["text"]}; margin-bottom: 12px;">'
            f'Economic Value Density Formulation'
            f'</h3>',
            unsafe_allow_html=True,
        )
        formula_html = (
            f'<div class="decision-card" style="padding: 18px; margin-bottom: 14px; border-radius: 10px; background: {c["card_bg"]}; border: 1px solid {c["card_border"]};">'
            f'<span style="font-size: 11px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase;">OBJECT UTILITY VALUE (GDSF FORMULA)</span>'
            f'<div style="font-family: monospace; font-size: 16px; font-weight: 800; color: {c["cyan"]}; margin: 10px 0; background: {c["card_bg_elevated"]}; padding: 10px 14px; border-radius: 6px; border: 1px solid {c["card_border"]};">'
            f'Utility(i) = L + (Cost(i) &times; Freq(i)) / Size(i)'
            f'</div>'
            f'<ul style="font-size: 12px; color: {c["text_muted"]}; margin: 8px 0 0 18px; line-height: 1.6;">'
            f'<li><b>L:</b> Aging inflation clock preventing stale object accumulation.</li>'
            f'<li><b>Cost(i):</b> Retrieval latency penalty and backend compute expenditure.</li>'
            f'<li><b>Freq(i):</b> Access velocity in the observation window.</li>'
            f'<li><b>Size(i):</b> RAM memory footprint (bytes).</li>'
            f'</ul>'
            f'</div>'
        )
        st.markdown(formula_html, unsafe_allow_html=True)

    with col_signals:
        st.markdown(
            f'<h3 style="font-size: 1.15rem; font-weight: 700; color: {c["text"]}; margin-bottom: 12px;">'
            f'Signal Classification Taxonomy'
            f'</h3>',
            unsafe_allow_html=True,
        )
        tax_html = (
            f'<div class="hero-card" style="padding: 18px; border-radius: 10px; background: {c["card_bg"]}; border: 1px solid {c["card_border"]};">'
            f'<div style="margin-bottom: 12px;">'
            f'<span style="background: rgba(16, 185, 129, 0.15); color: {c["emerald"]}; padding: 2px 7px; border-radius: 4px; font-size: 10px; font-weight: 800;">[MEASURED]</span>'
            f'<div style="font-size: 12px; color: {c["text"]}; margin-top: 4px;">Directly gathered telemetry: backend retrieval duration (ms), total requests, cache hits, backend calls.</div>'
            f'</div>'
            f'<div style="margin-bottom: 12px;">'
            f'<span style="background: rgba(56, 189, 248, 0.15); color: {c["cyan"]}; padding: 2px 7px; border-radius: 4px; font-size: 10px; font-weight: 800;">[DERIVED]</span>'
            f'<div style="font-size: 12px; color: {c["text"]}; margin-top: 4px;">Computed telemetry combinations: cumulative time saved (hits &times; latency), hit/miss percentages, offload ratio.</div>'
            f'</div>'
            f'<div>'
            f'<span style="background: rgba(168, 85, 247, 0.15); color: {c["purple"]}; padding: 2px 7px; border-radius: 4px; font-size: 10px; font-weight: 800;">[PROJECTED]</span>'
            f'<div style="font-size: 12px; color: {c["text"]}; margin-top: 4px;">Simulated economic savings: waiting for Person 1 adaptive engine integration and backend monetary API exposure.</div>'
            f'</div>'
            f'</div>'
        )
        st.markdown(tax_html, unsafe_allow_html=True)
