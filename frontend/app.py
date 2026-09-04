import os
import streamlit as st

from frontend.components.styles import (
    apply_global_styles,
    render_sidebar_branding,
    get_theme_colors,
)

st.set_page_config(
    page_title="Adaptive Cache Engine",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()
render_sidebar_branding(active_page="home")

c = get_theme_colors()

# --------------------------------------------------
# FLOATING SYSTEM STATUS DOCK
# --------------------------------------------------
dock_html = (
    f'<div class="floating-dock">'
    f'<div style="display:flex;align-items:center;">'
    f'<span class="pulse-dot"></span>'
    f'<span style="font-weight:700;font-size:12px;letter-spacing:0.8px;color:#10B981;">ENGINE ONLINE</span>'
    f'<span style="color:{c["text_subtle"]};margin:0 10px;">|</span>'
    f'<span style="color:{c["text_muted"]};font-size:12px;">Redis In-Memory Tier Connected &bull; Workload Agnostic Policy Active</span>'
    f'</div>'
    f'<div><span class="badge-pill badge-active">VH26 SATYAGRAH BUILD</span></div>'
    f'</div>'
)
st.markdown(dock_html, unsafe_allow_html=True)

# --------------------------------------------------
# MAIN TITLE
# --------------------------------------------------
title_gradient = (
    "linear-gradient(90deg, #FFFFFF 0%, #94A3B8 100%)"
    if c["is_dark"]
    else "linear-gradient(90deg, #0F172A 0%, #475569 100%)"
)
st.markdown(
    f'<h1 style="font-size:2.6rem;font-weight:800;margin:0 0 4px 0;background:{title_gradient};-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Adaptive Cache Management System</h1>'
    f'<p style="font-size:1.05rem;color:{c["text_muted"]};margin-bottom:22px;">Context-aware, cost-driven caching engine moving beyond static LRU/LFU heuristics.</p>',
    unsafe_allow_html=True,
)

# --------------------------------------------------
# HERO METRICS RIBBON
# --------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
with m1:
    h1_html = (
        f'<div class="hero-card floating-element">'
        f'<div style="color:{c["text_subtle"]};font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;">Cache Hit Rate</div>'
        f'<div style="font-size:28px;font-weight:800;color:{c["emerald"]};margin-top:4px;">89.6%</div>'
        f'<div style="color:{c["text_muted"]};font-size:11.5px;margin-top:4px;">&uarr; +11.2% vs baseline LRU</div>'
        f'</div>'
    )
    st.markdown(h1_html, unsafe_allow_html=True)

with m2:
    h2_html = (
        f'<div class="hero-card">'
        f'<div style="color:{c["text_subtle"]};font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;">P95 Read Latency</div>'
        f'<div style="font-size:28px;font-weight:800;color:{c["cyan"]};margin-top:4px;">27.3 ms</div>'
        f'<div style="color:{c["text_muted"]};font-size:11.5px;margin-top:4px;">Down from 42.5 ms</div>'
        f'</div>'
    )
    st.markdown(h2_html, unsafe_allow_html=True)

with m3:
    h3_html = (
        f'<div class="hero-card">'
        f'<div style="color:{c["text_subtle"]};font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;">Hourly Recompute Spend</div>'
        f'<div style="font-size:28px;font-weight:800;color:{c["amber"]};margin-top:4px;">$11.20</div>'
        f'<div style="color:{c["emerald"]};font-size:11.5px;margin-top:4px;">Saved $7.20 / hour</div>'
        f'</div>'
    )
    st.markdown(h3_html, unsafe_allow_html=True)

with m4:
    h4_html = (
        f'<div class="hero-card floating-element">'
        f'<div style="color:{c["text_subtle"]};font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.6px;">Capacity Allocation</div>'
        f'<div style="font-size:28px;font-weight:800;color:{c["purple"]};margin-top:4px;">512 MB</div>'
        f'<div style="color:{c["text_muted"]};font-size:11.5px;margin-top:4px;">Elastic Scaling Armed</div>'
        f'</div>'
    )
    st.markdown(h4_html, unsafe_allow_html=True)

st.write("")
st.write("")

# --------------------------------------------------
# CORE ARCHITECTURE PILLARS & LIVE DECISION STREAM
# --------------------------------------------------
col_pillars, col_feed = st.columns([1.5, 1.5])

with col_pillars:
    st.markdown("### Core Subsystems")

    p1_html = (
        f'<div class="hero-card" style="margin-bottom:12px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="font-size:14px;font-weight:700;color:{c["text"]};">Multi-Factor Adaptive Engine</span>'
        f'<span class="badge-pill badge-protected">ACTIVE</span>'
        f'</div>'
        f'<p style="color:{c["text_muted"]};font-size:12.5px;margin:8px 0 0 0;line-height:1.5;">Calculates retention scores dynamically using miss penalty latency, recompute API cost, and object memory footprint.</p>'
        f'</div>'
    )
    st.markdown(p1_html, unsafe_allow_html=True)

    p2_html = (
        f'<div class="hero-card" style="margin-bottom:12px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="font-size:14px;font-weight:700;color:{c["text"]};">Redis In-Memory Tier</span>'
        f'<span class="badge-pill badge-protected">HEALTHY</span>'
        f'</div>'
        f'<p style="color:{c["text_muted"]};font-size:12.5px;margin:8px 0 0 0;line-height:1.5;">Low-latency execution layer storing live cached values with background asynchronous stale-data recomputation.</p>'
        f'</div>'
    )
    st.markdown(p2_html, unsafe_allow_html=True)

    p3_html = (
        f'<div class="hero-card">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<span style="font-size:14px;font-weight:700;color:{c["text"]};">Telemetry & Scaling Arbiter</span>'
        f'<span class="badge-pill badge-active">MONITORING</span>'
        f'</div>'
        f'<p style="color:{c["text_muted"]};font-size:12.5px;margin:8px 0 0 0;line-height:1.5;">Evaluates marginal economic return: only expands cache memory when API cost savings outweigh RAM infrastructure cost.</p>'
        f'</div>'
    )
    st.markdown(p3_html, unsafe_allow_html=True)

with col_feed:
    st.markdown("### Live Decision Stream")
    feed_html = (
        f'<div class="terminal-box">'
        f'<span style="color:{c["text_subtle"]};">[15:58:10]</span> <span style="color:#10B981;">EVAL_CYCLE:</span> Processed 1,240 keys in 1.2ms.<br>'
        f'<span style="color:{c["text_subtle"]};">[15:58:12]</span> <span style="color:#F59E0B;">RETAIN_HIGH_COST:</span> Key <code>rec:dnn:feed_v2</code> cost $0.082 &gt; locked in RAM.<br>'
        f'<span style="color:{c["text_subtle"]};">[15:58:15]</span> <span style="color:#F43F5E;">EVICT_LOW_UTILITY:</span> Evicted <code>media:thumb:banner_v3</code> (Saved 2.4MB, Latency 8ms).<br>'
        f'<span style="color:{c["text_subtle"]};">[15:58:18]</span> <span style="color:{c["cyan"]};">X-FETCH_EARLY:</span> Probabilistic refresh triggered for <code>pricing:surge</code>.<br>'
        f'<span style="color:{c["text_subtle"]};">[15:58:21]</span> <span style="color:#10B981;">SCALING_CHECK:</span> Marginal utility +28.4% ROI. Capacity target: 512MB.<br>'
        f'<div style="margin-top:10px;border-top:1px dashed {c["card_border"]};padding-top:8px;color:{c["text_muted"]};font-size:11px;">● Stream active &bull; Scoring queue latency: 0.4ms &bull; 0 dropped evictions</div>'
        f'</div>'
    )
    st.markdown(feed_html, unsafe_allow_html=True)

st.write("")
st.divider()

# --------------------------------------------------
# QUICK EVALUATION SHORTCUTS
# --------------------------------------------------
st.markdown("### Quick Evaluation Shortcuts")
cta1, cta2, cta3 = st.columns(3)

with cta1:
    if st.button(
        "View Policy Benchmarks (LRU vs GDS vs Adaptive)",
        width="stretch",
        type="primary",
    ):
        st.switch_page("pages/5_Benchmarks.py")

with cta2:
    if st.button("Trigger Workload Stress Simulation", width="stretch"):
        st.switch_page("pages/4_Workload.py")

with cta3:
    if st.button("Inspect Real-Time Eviction Queue", width="stretch"):
        st.switch_page("pages/3_Adaptive_Decisions.py")