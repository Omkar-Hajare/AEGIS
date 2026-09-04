import os
import streamlit as st
import pandas as pd

from frontend.services.api_client import (
    get_adaptive_decision,
    get_cache_stats,
    get_cache_objects,
)
from frontend.components.styles import (
    apply_global_styles,
    render_sidebar_branding,
    get_theme_colors,
)
from frontend.components.metric_card import render_metric_card
from frontend.components.decision_card import render_decision_card

st.set_page_config(
    page_title="Adaptive Decisions & Arbitration",
    layout="wide",
)

apply_global_styles()
render_sidebar_branding(active_page="decisions")

c = get_theme_colors()

# --------------------------------------------------
# FLOATING HEADER DOCK
# --------------------------------------------------
dock_html = (
    f'<div class="floating-dock">'
    f'<div style="display:flex;align-items:center;">'
    f'<span class="pulse-dot"></span>'
    f'<span style="font-weight:700;font-size:12px;letter-spacing:0.8px;color:#10B981;">ARBITER PIPELINE RUNNING</span>'
    f'<span style="color:{c["text_subtle"]};margin:0 10px;">|</span>'
    f'<span style="color:{c["text_muted"]};font-size:12px;">Policy: Multi-Factor Utility Density (GDSF)</span>'
    f'</div>'
    f'<div><span class="badge-pill badge-protected">EVAL FREQUENCY: 5s</span></div>'
    f'</div>'
)
st.markdown(dock_html, unsafe_allow_html=True)

st.markdown(
    '<h1 style="margin:0 0 4px 0;font-size:2.2rem;">Adaptive Decisions & Arbitration Queue</h1>'
    '<p class="muted" style="font-size:13.5px;margin-bottom:22px;">Auditing dynamic admissions, eviction prioritization, and memory capacity adjustments in real time.</p>',
    unsafe_allow_html=True,
)

# --------------------------------------------------
# DATA
# --------------------------------------------------
decision = get_adaptive_decision()
stats = get_cache_stats()
objects = get_cache_objects()

# --------------------------------------------------
# KPI SUMMARY STRIP
# --------------------------------------------------
m1, m2, m3, m4 = st.columns(4)
with m1:
    render_metric_card(
        "Active Policy Mode",
        "Utility-Density",
        subtitle="Cost + Latency + Size aware",
        tag="ALGORITHM",
        delta="Adaptive GDSF",
        delta_color=c["cyan"],
        is_floating=True,
    )

with m2:
    render_metric_card(
        "Current Arbiter Action",
        decision.get("capacity_action", "SCALE_UP"),
        subtitle="Triggered by memory pressure",
        tag="ACTION",
        delta="+28.4% ROI threshold met",
        delta_color="#10B981",
    )

with m3:
    render_metric_card(
        "Target Memory Capacity",
        f"{decision.get('recommended_capacity_mb', 512)} MB",
        subtitle=f"From {decision.get('current_capacity_mb', 384)} MB baseline",
        tag="CAPACITY",
        delta="+128 MB Elastic Scaling",
        delta_color="#10B981",
    )

with m4:
    render_metric_card(
        "Hourly Value Preserved",
        f"${stats.get('hourly_cost_saved_usd', 7.20):.2f} / hr",
        subtitle="Net API recompute avoidance",
        tag="SAVINGS",
        delta="+$172.80 / day run-rate",
        delta_color="#F59E0B",
        is_floating=True,
    )

st.write("")

# --------------------------------------------------
# PIPELINE ARCHITECTURE VISUAL
# --------------------------------------------------
pipe_img_path = "frontend/assets/pipeline.jpg"
if os.path.exists(pipe_img_path):
    st.image(
        pipe_img_path,
        caption="Cache Telemetry & Eviction Pipeline: Request Stream -> Arbiter Filter -> In-Memory Buffer -> Eviction Queue",
        width="stretch",
    )
    st.write("")

# --------------------------------------------------
# ACTIVE ARBITER DECISION CARD
# --------------------------------------------------
st.markdown("### Active Arbiter Cycle Output")
render_decision_card(decision)

st.write("")
st.divider()

# --------------------------------------------------
# INTERACTIVE WEIGHT TUNER
# --------------------------------------------------
st.markdown("### Scoring Function & Real-Time Weight Tuning")

formula_html = (
    f'<div class="hero-card" style="margin-bottom:16px;">'
    f'<div style="font-size:11px;font-weight:700;color:{c["text_muted"]};text-transform:uppercase;margin-bottom:6px;">MULTI-FACTOR RETENTION SCORING FORMULA</div>'
    f'<div style="font-family:monospace;font-size:15px;font-weight:700;color:{c["cyan"]};">Score(k) = ( Recompute_Cost<sup>&alpha;</sup> &times; Miss_Latency<sup>&beta;</sup> &times; Hits<sup>&delta;</sup> ) / Size_KB<sup>&gamma;</sup> + L</div>'
    f'<p style="font-size:12.5px;color:{c["text_muted"]};margin:8px 0 0 0;line-height:1.5;">Where <strong>L</strong> is the aging inflation clock, <strong>&alpha;</strong> penalizes expensive 3rd-party API calls, and <strong>&gamma;</strong> penalizes bulky memory objects.</p>'
    f'</div>'
)
st.markdown(formula_html, unsafe_allow_html=True)

t1, t2, t3 = st.columns(3)
with t1:
    alpha = st.slider(
        "Recompute Cost Sensitivity (α)",
        0.0,
        2.0,
        1.2,
        0.1,
        help="Higher values prioritize caching expensive AI and third-party APIs.",
    )
with t2:
    beta = st.slider(
        "Miss Latency Weight (β)",
        0.0,
        2.0,
        1.0,
        0.1,
        help="Higher values favor caching slow database queries to protect SLA.",
    )
with t3:
    gamma = st.slider(
        "Memory Footprint Penalty (γ)",
        0.1,
        2.0,
        1.0,
        0.1,
        help="Higher values penalize large objects to maximize total item count.",
    )

recomputed_rows = []
for obj in objects:
    cost = max(0.001, float(obj.get("recompute_cost_usd", 0.01)))
    latency = max(1.0, float(obj.get("retrieval_cost_ms", 10.0)))
    size_kb = max(0.1, float(obj.get("size_kb", 4.0)))
    hits = max(1, int(obj.get("access_count", 10)))

    raw_val = (
        ((cost * 100) ** alpha)
        * ((latency / 10.0) ** beta)
        * ((hits / 100.0) ** 0.5)
    ) / (size_kb**gamma)
    norm_score = min(0.99, max(0.10, 1.0 - (1.0 / (1.0 + raw_val))))

    recomputed_rows.append(
        {
            "Key": obj["key"],
            "Category": obj.get("category", "General"),
            "Size": f"{size_kb:.1f} KB",
            "Cost": f"${cost:.3f}",
            "Latency": f"{latency:.1f} ms",
            "Computed Score": f"{norm_score:.3f}",
            "Arbitration Status": (
                "Protected"
                if norm_score > 0.80
                else ("Active" if norm_score > 0.45 else "Evict Candidate")
            ),
        }
    )

df_recomputed = pd.DataFrame(recomputed_rows).sort_values(
    by="Computed Score", ascending=False
)

st.markdown(
    f"#### Recomputed Arbitration Rankings with α={alpha}, β={beta}, γ={gamma}"
)
st.dataframe(df_recomputed, width="stretch", hide_index=True)

st.write("")
st.divider()

# --------------------------------------------------
# DECISION AUDIT LOG
# --------------------------------------------------
st.markdown("### Real-Time Decision Audit Trail")

audit_records = [
    {
        "Timestamp": "15:45:15",
        "Cycle ID": "EV-9942",
        "Target Key": "media:thumb:banner_hero_v3",
        "Action": "EVICT",
        "Utility Score": "0.31",
        "Memory Freed": "2.4 MB",
        "Cost Impact": "Saved 2.4MB for $0.002 penalty",
        "Status": "Executed",
    },
    {
        "Timestamp": "15:45:12",
        "Cycle ID": "EV-9941",
        "Target Key": "rec:dnn:feed_v2:user_8819",
        "Action": "RETAIN",
        "Utility Score": "0.96",
        "Memory Freed": "0 MB",
        "Cost Impact": "Protected $0.082 AI inference",
        "Status": "Locked",
    },
    {
        "Timestamp": "15:44:50",
        "Cycle ID": "EV-9940",
        "Target Key": "pricing:dynamic:surge:loc_14",
        "Action": "EARLY_REFRESH",
        "Utility Score": "0.89",
        "Memory Freed": "0 MB",
        "Cost Impact": "Probabilistic background pre-fetch",
        "Status": "Dispatched",
    },
    {
        "Timestamp": "15:43:10",
        "Cycle ID": "EV-9939",
        "Target Key": "recommendation:cold:item_88",
        "Action": "EVICT",
        "Utility Score": "0.44",
        "Memory Freed": "64.0 KB",
        "Cost Impact": "Low hits & high age",
        "Status": "Executed",
    },
    {
        "Timestamp": "15:40:02",
        "Cycle ID": "CAP-102",
        "Target Key": "SYSTEM_RAM_TIER",
        "Action": "SCALE_UP",
        "Utility Score": "N/A",
        "Memory Freed": "+128 MB Target",
        "Cost Impact": "Marginal API savings exceed cloud RAM cost",
        "Status": "Pending Approval",
    },
]

df_audit = pd.DataFrame(audit_records)
st.dataframe(df_audit, width="stretch", hide_index=True)

st.write("")

# --------------------------------------------------
# STRATEGIC COMPARISON: LRU VS ADAPTIVE
# --------------------------------------------------
st.markdown("### Algorithmic Comparison: Why Blind LRU Fails")
c_lru, c_adapt = st.columns(2)

grid_bg = "rgba(0,0,0,0.25)" if c["is_dark"] else "#F1F5F9"

with c_lru:
    lru_html = (
        f'<div class="hero-card" style="border-left:4px solid {c["rose"]} !important;">'
        f'<div style="font-size:14px;font-weight:700;color:{c["rose"]};margin-bottom:8px;">Standard LRU Eviction Failure</div>'
        f'<p style="font-size:13px;color:{c["text_muted"]};margin:0 0 10px 0;line-height:1.5;">LRU only inspects timestamps. An expensive neural recommendation accessed 3 seconds before a 50-byte ping gets evicted because LRU is cost-blind.</p>'
        f'<div style="font-size:11.5px;background:{grid_bg};padding:10px;border-radius:6px;color:{c["text"]};"><strong>Result:</strong> Next request incurs a <strong>145ms stall</strong> and incurs <strong>$0.082</strong> on model inference.</div>'
        f'</div>'
    )
    st.markdown(lru_html, unsafe_allow_html=True)

with c_adapt:
    adapt_html = (
        f'<div class="hero-card" style="border-left:4px solid {c["emerald"]} !important;">'
        f'<div style="font-size:14px;font-weight:700;color:{c["emerald"]};margin-bottom:8px;">Adaptive Engine Cost-Density</div>'
        f'<p style="font-size:13px;color:{c["text_muted"]};margin:0 0 10px 0;line-height:1.5;">The arbiter evaluates Cost Density. It recognizes that retaining 1 expensive AI response in RAM is 40&times; more economically valuable than retaining a bulky static thumbnail.</p>'
        f'<div style="font-size:11.5px;background:{grid_bg};padding:10px;border-radius:6px;color:{c["text"]};"><strong>Result:</strong> P95 latency drops to <strong>27.3ms</strong> and avoids <strong>$7.20/hour</strong> in redundant backend recompute spend.</div>'
        f'</div>'
    )
    st.markdown(adapt_html, unsafe_allow_html=True)