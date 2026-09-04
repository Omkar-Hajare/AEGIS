import streamlit as st
import pandas as pd

from frontend.services.api_client import get_cache_objects, get_cache_stats
from frontend.components.styles import (
    apply_global_styles,
    render_sidebar_branding,
    get_theme_colors,
)
from frontend.components.metric_card import render_metric_card
from frontend.components.charts import (
    render_scatter_bubble_chart,
    render_comparison_bar_chart,
)

st.set_page_config(
    page_title="Cache Objects & Retention Tiers",
    layout="wide",
)

apply_global_styles()
render_sidebar_branding(active_page="cache_objects")

c = get_theme_colors()

# --------------------------------------------------
# STATE MANAGEMENT
# --------------------------------------------------
if "cache_objects_data" not in st.session_state:
    st.session_state["cache_objects_data"] = [
        dict(item) for item in get_cache_objects()
    ]

raw_objects = st.session_state["cache_objects_data"]
stats = get_cache_stats()
df_all = pd.DataFrame(raw_objects)

# --------------------------------------------------
# FLOATING DOCK HEADER
# --------------------------------------------------
dock_html = (
    f'<div class="floating-dock">'
    f'<div style="display:flex;align-items:center;">'
    f'<span class="pulse-dot"></span>'
    f'<span style="font-weight:700;font-size:12px;letter-spacing:0.8px;color:#10B981;">TIER 1 IN-MEMORY OBJECTS</span>'
    f'<span style="color:{c["text_subtle"]};margin:0 10px;">|</span>'
    f'<span style="color:{c["text_muted"]};font-size:12px;">Active Objects: {len(df_all)} Keys Monitored</span>'
    f'</div>'
    f'<div><span class="badge-pill badge-protected">GDSF DENSITY ACTIVE</span></div>'
    f'</div>'
)
st.markdown(dock_html, unsafe_allow_html=True)

st.markdown(
    '<h1 style="margin:0 0 4px 0;font-size:2.2rem;">Cache Objects & Retention Tiers</h1>'
    '<p class="muted" style="font-size:13.5px;margin-bottom:22px;">Inspect memory footprint, recompute penalty, and multi-factor retention scores assigned by the Adaptive Engine.</p>',
    unsafe_allow_html=True,
)

# --------------------------------------------------
# HERO METRICS STRIP
# --------------------------------------------------
k1, k2, k3, k4 = st.columns(4)

total_keys = len(df_all)
protected_count = len(
    df_all[df_all["status"].str.contains("Protected|Refreshed", na=False)]
)
eviction_count = len(
    df_all[df_all["status"].str.contains("Eviction|Risk", na=False)]
)
avg_score = df_all["utility_score"].mean() if not df_all.empty else 0.0

with k1:
    render_metric_card(
        "Active Cache Keys",
        f"{total_keys:,}",
        subtitle="Tier-1 In-Memory registry",
        tag="OBJECTS",
        delta="Managed by Arbiter",
        delta_color=c["cyan"],
        is_floating=True,
    )

with k2:
    render_metric_card(
        "High-Cost Protected",
        f"{protected_count} Keys",
        subtitle="Locked against blind eviction",
        tag="PRIORITY",
        delta="API Recompute Shield",
        delta_color="#10B981",
    )

with k3:
    render_metric_card(
        "Eviction Candidates",
        f"{eviction_count} Keys",
        subtitle="Low cost-to-size density",
        tag="AT RISK",
        delta="Scheduled for pruning",
        delta_color="#F43F5E",
    )

with k4:
    render_metric_card(
        "Mean Utility Score",
        f"{avg_score:.2f} / 1.0",
        subtitle="Normalized GDSF Score",
        tag="SCORING",
        delta="+28% vs plain LRU",
        delta_color="#10B981",
        is_floating=True,
    )

st.write("")

# --------------------------------------------------
# MULTI-FACTOR UTILITY MAP (SCATTER BUBBLE)
# --------------------------------------------------
st.markdown("### Multi-Factor Retention Landscape")
st.caption(
    "Bubble size represents access frequency. High-cost items are protected in top-left; bulky low-value objects in bottom-right are scheduled for eviction."
)

if not df_all.empty:
    render_scatter_bubble_chart(
        df=df_all,
        x_col="size_kb",
        y_col="recompute_cost_usd",
        size_col="access_count",
        color_col="status",
        hover_name="key",
        title="Cost Density Distribution (Recompute Cost $ vs Memory Size KB)",
        x_title="Memory Footprint (KB)",
        y_title="Recompute Cost ($ USD)",
        height=360,
    )
else:
    st.info("No cache objects currently stored.")

st.write("")
st.divider()

# --------------------------------------------------
# SEARCH, FILTER & DIAGNOSTIC INSPECTOR
# --------------------------------------------------
st.markdown("### Key Registry & Diagnostic Inspector")

fc1, fc2, fc3, fc4 = st.columns([1.6, 1, 1, 1])

with fc1:
    search_query = st.text_input(
        "Filter by Key Name",
        placeholder="Filter by prefix (e.g. rec: or user:)",
        label_visibility="collapsed",
    )

with fc2:
    cats = (
        ["All Categories"] + sorted(list(df_all["category"].unique()))
        if "category" in df_all
        else ["All Categories"]
    )
    selected_cat = st.selectbox("Category", cats, label_visibility="collapsed")

with fc3:
    statuses = (
        ["All Statuses"] + sorted(list(df_all["status"].unique()))
        if not df_all.empty
        else ["All Statuses"]
    )
    selected_status = st.selectbox(
        "Status", statuses, label_visibility="collapsed"
    )

with fc4:
    sort_option = st.selectbox(
        "Sort By",
        [
            "Utility Score (High to Low)",
            "Recompute Cost (High to Low)",
            "Size (Large to Small)",
            "Hits (High to Low)",
        ],
        label_visibility="collapsed",
    )

# Apply filters
filtered_df = df_all.copy()
if search_query and not filtered_df.empty:
    filtered_df = filtered_df[
        filtered_df["key"].str.contains(search_query, case=False, na=False)
    ]
if selected_cat != "All Categories" and not filtered_df.empty:
    filtered_df = filtered_df[filtered_df["category"] == selected_cat]
if selected_status != "All Statuses" and not filtered_df.empty:
    filtered_df = filtered_df[filtered_df["status"] == selected_status]

if not filtered_df.empty:
    if sort_option == "Utility Score (High to Low)":
        filtered_df = filtered_df.sort_values(
            by="utility_score", ascending=False
        )
    elif sort_option == "Recompute Cost (High to Low)":
        filtered_df = filtered_df.sort_values(
            by="recompute_cost_usd", ascending=False
        )
    elif sort_option == "Size (Large to Small)":
        filtered_df = filtered_df.sort_values(by="size_kb", ascending=False)
    elif sort_option == "Hits (High to Low)":
        filtered_df = filtered_df.sort_values(
            by="access_count", ascending=False
        )

st.write("")

# Side-by-side Table and Inspector
col_table, col_inspect = st.columns([1.6, 1.4])

with col_table:
    st.markdown(f"#### Registry ({len(filtered_df)} objects matching)")

    if not filtered_df.empty:
        display_df = filtered_df.copy()
        display_df["Size"] = display_df["size_kb"].apply(
            lambda s: f"{s:.1f} KB" if s < 1024 else f"{s/1024:.1f} MB"
        )
        display_df["Cost"] = display_df["recompute_cost_usd"].apply(
            lambda c: f"${c:.3f}"
        )
        display_df["Latency"] = display_df["retrieval_cost_ms"].apply(
            lambda l: f"{l:.1f} ms"
        )
        display_df["Score"] = display_df["utility_score"].apply(
            lambda sc: f"{sc:.2f}"
        )

        cols = [
            "key",
            "category",
            "Size",
            "access_count",
            "Cost",
            "Latency",
            "Score",
            "status",
        ]
        rename_dict = {
            "key": "Object Key",
            "category": "Category",
            "access_count": "Hits",
            "status": "State",
        }

        st.dataframe(
            display_df[cols].rename(columns=rename_dict),
            width="stretch",
            hide_index=True,
            height=380,
        )
    else:
        st.info("No cache objects match the filter criteria.")

    if st.button("Reset Cache Objects to Default", type="secondary"):
        st.session_state["cache_objects_data"] = [
            dict(item) for item in get_cache_objects()
        ]
        st.rerun()

with col_inspect:
    st.markdown("#### Key Diagnostic Inspector")

    key_options = list(filtered_df["key"].unique()) if not filtered_df.empty else []
    if not key_options:
        st.warning("No key selected.")
    else:
        selected_key = st.selectbox(
            "Select Key to Inspect", key_options, key="diagnostic_key_select"
        )

        idx = next(
            (
                i
                for i, item in enumerate(st.session_state["cache_objects_data"])
                if item["key"] == selected_key
            ),
            None,
        )

        if idx is not None:
            item = st.session_state["cache_objects_data"][idx]

            status_str = str(item["status"])
            if "Protected" in status_str or "Refreshed" in status_str:
                badge_class = "badge-protected"
            elif "Hot" in status_str:
                badge_class = "badge-hot"
            elif "Risk" in status_str or "Eviction" in status_str:
                badge_class = "badge-risk"
            else:
                badge_class = "badge-active"

            grid_bg = "rgba(0,0,0,0.25)" if c["is_dark"] else "#F1F5F9"
            diag_html = (
                f'<div class="hero-card" style="padding:16px;margin-bottom:14px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">'
                f'<span class="badge-pill {badge_class}">{item["status"]}</span>'
                f'<span style="font-size:11px;color:{c["text_muted"]};">Category: <strong>{item.get("category", "General")}</strong></span>'
                f'</div>'
                f'<div style="font-family:monospace;font-size:14px;font-weight:700;color:{c["cyan"]};word-break:break-all;margin-bottom:12px;">{item["key"]}</div>'
                f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:12px;background:{grid_bg};padding:12px;border-radius:8px;">'
                f'<div><div class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">Utility Score</div><div style="font-size:17px;font-weight:800;color:{c["emerald"]};">{item["utility_score"]:.2f} / 1.0</div></div>'
                f'<div><div class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">Recompute Cost</div><div style="font-size:17px;font-weight:800;color:{c["amber"]};">${item["recompute_cost_usd"]:.3f}</div></div>'
                f'<div><div class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">Memory Footprint</div><div style="font-size:14px;font-weight:700;color:{c["text"]};">{item["size_kb"]:.1f} KB</div></div>'
                f'<div><div class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">Backend Latency</div><div style="font-size:14px;font-weight:700;color:{c["cyan"]};">{item["retrieval_cost_ms"]:.1f} ms</div></div>'
                f'<div><div class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">Total Hits</div><div style="font-size:14px;font-weight:700;color:{c["text"]};">{item["access_count"]:,}</div></div>'
                f'<div><div class="muted" style="font-size:10px;font-weight:700;text-transform:uppercase;">TTL Remaining</div><div style="font-size:14px;font-weight:700;color:{c["text"]};">{item.get("ttl_remaining_s", 1200)}s</div></div>'
                f'</div>'
                f'</div>'
            )
            st.markdown(diag_html, unsafe_allow_html=True)

            act1, act2, act3 = st.columns(3)

            with act1:
                if st.button("X-Fetch Refresh", key="btn_xfetch", width="stretch"):
                    st.session_state["cache_objects_data"][idx][
                        "ttl_remaining_s"
                    ] = 3600
                    st.session_state["cache_objects_data"][idx][
                        "last_accessed"
                    ] = "Just now"
                    st.session_state["cache_objects_data"][idx][
                        "status"
                    ] = "Refreshed"
                    st.session_state["cache_objects_data"][idx][
                        "access_count"
                    ] += 1
                    st.toast(
                        f"Refreshed key `{selected_key}` with TTL 3600s."
                    )
                    st.rerun()

            with act2:
                if st.button("Lock in RAM", key="btn_lock", width="stretch"):
                    st.session_state["cache_objects_data"][idx][
                        "status"
                    ] = "Protected (Locked)"
                    st.session_state["cache_objects_data"][idx][
                        "utility_score"
                    ] = 0.99
                    st.session_state["cache_objects_data"][idx]["score"] = 0.99
                    st.toast(
                        f"Key `{selected_key}` locked in RAM with priority override."
                    )
                    st.rerun()

            with act3:
                if st.button("Evict Now", key="btn_evict", width="stretch"):
                    st.session_state["cache_objects_data"].pop(idx)
                    st.toast(
                        f"Evicted key `{selected_key}` from in-memory tier."
                    )
                    st.rerun()

st.write("")
st.divider()

# --------------------------------------------------
# CATEGORY DISTRIBUTION CHARTS
# --------------------------------------------------
if not df_all.empty and "category" in df_all:
    st.markdown("### Memory Footprint & Value Distribution by Category")
    cat_summary = (
        df_all.groupby("category")
        .agg(
            {
                "size_kb": "sum",
                "recompute_cost_usd": "sum",
                "access_count": "sum",
            }
        )
        .reset_index()
    )

    b1, b2 = st.columns(2)
    with b1:
        render_comparison_bar_chart(
            categories=list(cat_summary["category"]),
            values_dict={
                "Memory Footprint (KB)": list(cat_summary["size_kb"])
            },
            title="Total Memory Allocated by Category (KB)",
            y_title="Memory (KB)",
            unit=" KB",
            height=280,
        )

    with b2:
        render_comparison_bar_chart(
            categories=list(cat_summary["category"]),
            values_dict={
                "Recompute Cost Saved (Cents)": list(
                    cat_summary["recompute_cost_usd"] * 100
                )
            },
            title="Hourly Recompute Value Preserved (Cents)",
            y_title="Value (Cents)",
            unit="¢",
            height=280,
        )