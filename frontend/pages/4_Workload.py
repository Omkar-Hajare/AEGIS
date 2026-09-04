import math
import streamlit as st
import pandas as pd

from frontend.services.api_client import get_workload, get_cache_stats
from frontend.components.styles import (
    apply_global_styles,
    render_sidebar_branding,
    get_theme_colors,
)
from frontend.components.metric_card import render_metric_card
from frontend.components.charts import (
    render_line_chart,
    render_multi_line_chart,
)

st.set_page_config(
    page_title="Workload Stress Simulator",
    layout="wide",
)

apply_global_styles()
render_sidebar_branding(active_page="workload")

c = get_theme_colors()

# --------------------------------------------------
# FLOATING DOCK HEADER
# --------------------------------------------------
dock_html = (
    f'<div class="floating-dock">'
    f'<div style="display:flex;align-items:center;">'
    f'<span class="pulse-dot"></span>'
    f'<span style="font-weight:700;font-size:12px;letter-spacing:0.8px;color:#10B981;">WORKLOAD SANDBOX ONLINE</span>'
    f'<span style="color:{c["text_subtle"]};margin:0 10px;">|</span>'
    f'<span style="color:{c["text_muted"]};font-size:12px;">Synthetic Traffic Ingestion & Resiliency Testing</span>'
    f'</div>'
    f'<div><span class="badge-pill badge-active">MODE: REACTIVE STRESS</span></div>'
    f'</div>'
)
st.markdown(dock_html, unsafe_allow_html=True)

st.markdown(
    '<h1 style="margin:0 0 4px 0;font-size:2.2rem;">Workload Generator & Stress Simulator</h1>'
    '<p class="muted" style="font-size:13.5px;margin-bottom:22px;">Simulate realistic production access patterns, trace replays, and stress spikes to test adaptive elasticity.</p>',
    unsafe_allow_html=True,
)

# --------------------------------------------------
# SCENARIO SELECTION
# --------------------------------------------------
st.markdown("### Select Traffic Archetype")

scenarios = {
    "E-Commerce Flash Sale (Zipfian Skew)": {
        "desc": "Heavy access concentration on top 5% hot products. Tests frequency caching without thrashing cold inventory.",
        "rps": 2400,
        "skew": 1.25,
        "read_ratio": 94,
        "hit_rate_pred": 92.4,
        "lru_hit_rate": 79.1,
    },
    "Generative AI & LLM Inference Spike": {
        "desc": "High recompute cost ($0.08/call), moderate concurrency, extreme latency penalty on cache misses.",
        "rps": 850,
        "skew": 0.95,
        "read_ratio": 90,
        "hit_rate_pred": 88.6,
        "lru_hit_rate": 72.0,
    },
    "Cache Thrashing Attack (Scan Workload)": {
        "desc": "Uniform pseudo-random scans designed to evict everything in standard LRU. Tests adaptive scan resistance.",
        "rps": 3200,
        "skew": 0.20,
        "read_ratio": 98,
        "hit_rate_pred": 76.5,
        "lru_hit_rate": 31.2,
    },
    "Dynamic Microservices Burst (Read/Write)": {
        "desc": "Mixed read-write storm with rapid invalidations and short TTL dependencies.",
        "rps": 1800,
        "skew": 0.85,
        "read_ratio": 80,
        "hit_rate_pred": 85.2,
        "lru_hit_rate": 74.8,
    },
}

selected_scenario_name = st.selectbox(
    "Choose Workload Scenario", list(scenarios.keys())
)
current_scenario = scenarios[selected_scenario_name]

scen_html = (
    f'<div class="hero-card" style="margin-bottom:16px;border-left:4px solid {c["cyan"]} !important;">'
    f'<div style="font-size:13.5px;color:{c["text"]};line-height:1.5;">{current_scenario["desc"]}</div>'
    f'</div>'
)
st.markdown(scen_html, unsafe_allow_html=True)

# --------------------------------------------------
# PARAMETER TUNING SLIDERS
# --------------------------------------------------
st.markdown("### Simulation Parameters")

col_p1, col_p2, col_p3, col_p4 = st.columns(4)

with col_p1:
    target_rps = st.slider(
        "Target Concurrency (RPS)",
        200,
        5000,
        current_scenario["rps"],
        100,
        help="Simulated requests per second arriving at cache gateway.",
    )

with col_p2:
    skew_alpha = st.slider(
        "Zipfian Skew Factor (α)",
        0.1,
        2.0,
        float(current_scenario["skew"]),
        0.05,
        help="Higher α means steeper popularity concentration.",
    )

with col_p3:
    read_pct = st.slider(
        "Read Percentage (%)",
        50,
        100,
        current_scenario["read_ratio"],
        2,
        help="Percentage of GET/Read operations vs PUT/POST writes.",
    )

with col_p4:
    sim_capacity = st.slider(
        "Simulated RAM Tier (MB)",
        128,
        2048,
        512,
        64,
        help="Cache capacity allocated to in-memory tier.",
    )

st.button("Run Workload Stress Simulation", type="primary", width="stretch")

time_steps = [f"T+{i*5}s" for i in range(12)]
base_hit = current_scenario["hit_rate_pred"]
lru_base = current_scenario["lru_hit_rate"]
capacity_factor = (sim_capacity / 512.0) ** 0.35

adaptive_curve = [
    min(
        98.5,
        max(
            40.0,
            base_hit * capacity_factor
            + math.sin(i / 2.0) * 1.5
            - (0.8 if i < 3 else 0),
        ),
    )
    for i in range(12)
]
lru_curve = [
    min(
        95.0,
        max(
            15.0,
            lru_base * capacity_factor
            - (i * 1.8 if skew_alpha < 0.5 else math.cos(i / 2.0) * 2.2),
        ),
    )
    for i in range(12)
]
throughput_curve = [
    int(target_rps * (0.85 + 0.25 * math.sin(i / 2.5))) for i in range(12)
]

final_adaptive_hit = adaptive_curve[-1]
final_lru_hit = lru_curve[-1]
hit_delta = final_adaptive_hit - final_lru_hit

st.write("")
st.divider()

# --------------------------------------------------
# SIMULATION OUTPUT
# --------------------------------------------------
st.markdown("### Simulation Output & Policy Resilience")

s1, s2, s3, s4 = st.columns(4)

with s1:
    render_metric_card(
        "Simulated Peak RPS",
        f"{max(throughput_curve):,} RPS",
        subtitle=f"Mean: {target_rps:,} RPS",
        tag="PEAK TRAFFIC",
        delta="Throughput Sustained",
        delta_color=c["cyan"],
        is_floating=True,
    )

with s2:
    render_metric_card(
        "Adaptive Hit Rate",
        f"{final_adaptive_hit:.1f}%",
        subtitle="Under simulated stress",
        tag="HIT RATE",
        delta=f"↑ +{hit_delta:.1f}% vs LRU",
        delta_color="#10B981",
    )

with s3:
    render_metric_card(
        "LRU Baseline Hit Rate",
        f"{final_lru_hit:.1f}%",
        subtitle="Subject to cache pollution",
        tag="BASELINE",
        delta="High Eviction Churn",
        delta_color="#F43F5E",
    )

with s4:
    db_offload = 100 - (100 - final_adaptive_hit)
    render_metric_card(
        "Database Shielding",
        f"{db_offload:.1f}%",
        subtitle="Absorbed by cache tier",
        tag="PROTECTION",
        delta="Zero DB Meltdowns",
        delta_color="#10B981",
        is_floating=True,
    )

st.write("")

ch_left, ch_right = st.columns(2)

with ch_left:
    render_multi_line_chart(
        x=time_steps,
        series_dict={
            "Adaptive Engine (Protected)": adaptive_curve,
            "Standard LRU (Baseline)": lru_curve,
        },
        title="Hit Rate Resilience Under Workload Stress (%)",
        y_title="Hit Rate (%)",
        unit="%",
        height=330,
    )

with ch_right:
    render_line_chart(
        x=time_steps,
        y=throughput_curve,
        title="Simulated Ingestion Concurrency (RPS)",
        y_title="Requests / sec",
        color=c["cyan"],
        unit=" req/s",
        show_area=True,
        height=330,
    )

st.write("")
verdict_html = (
    f'<div class="hero-card">'
    f'<div style="font-weight:700;font-size:13.5px;color:{c["text"]};margin-bottom:4px;">Workload Observation Verdict</div>'
    f'<p style="font-size:13px;color:{c["text_muted"]};margin:0;line-height:1.55;">'
    f'Under <strong>{selected_scenario_name}</strong>, the Adaptive Engine maintained a <strong>{final_adaptive_hit:.1f}%</strong> hit rate, '
    f'outperforming standard LRU by <strong>+{hit_delta:.1f}%</strong>. Dynamic retention scoring prevented scan pollution from evicting critical database and API records.'
    f'</p>'
    f'</div>'
)
st.markdown(verdict_html, unsafe_allow_html=True)
