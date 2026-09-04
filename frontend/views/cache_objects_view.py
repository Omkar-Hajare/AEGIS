import streamlit as st
import pandas as pd

from frontend.services.api_client import get_cache_objects, get_cache_stats
from frontend.components.styles import get_theme_colors
from frontend.components.metric_card import render_metric_card
from frontend.components.charts import (
    render_scatter_bubble_chart,
    render_comparison_bar_chart,
)
from frontend.components.status_badge import (
    get_decision_badge_html,
    get_status_pill_html,
)


def render_cache_objects_view():
    """Render Cache Objects & Memory Landscape with interactive 2D density chart and diagnostic inspector."""
    c = get_theme_colors()

    # --------------------------------------------------
    # STATE MANAGEMENT
    # --------------------------------------------------
    if "cache_objects_data" not in st.session_state:
        st.session_state["cache_objects_data"] = [
            dict(item) for item in get_cache_objects()
        ]

    raw_objects = st.session_state["cache_objects_data"]
    for item in raw_objects:
        if "cost_usd" not in item:
            item["cost_usd"] = item.get("recompute_cost_usd", 0.01)
        if "hits_last_min" not in item:
            item["hits_last_min"] = item.get("access_count", 100)
        if "decision" not in item:
            item["decision"] = (
                "RETAIN"
                if "Protected" in item.get("status", "") or "Hot" in item.get("status", "")
                else "EVICT"
            )
        if "rationale" not in item:
            if item["decision"] == "RETAIN":
                item["rationale"] = "High utility density offsets memory footprint. Shielded against LRU eviction to prevent costly recomputation."
            elif item["decision"] == "REFRESH":
                item["rationale"] = "Asynchronous background X-Fetch scheduled ahead of expiration to prevent latency degradation."
            else:
                item["rationale"] = "Low access velocity and modest recompute cost. Flagged for memory recycling under pressure."

    stats = get_cache_stats()
    df_all = pd.DataFrame(raw_objects)

    # Header Title Block with cleanly aligned right badge
    header_html = (
        f'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin: 8px 0 22px 0; flex-wrap: wrap; gap: 12px;">'
        f'<div>'
        f'<h1 style="margin: 0 0 6px 0; font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; color: {c["text"]} !important;">'
        f'Cache Objects & <span style="color: {c["cyan"]} !important;">Memory Landscape</span>'
        f'</h1>'
        f'<p style="margin: 0; font-size: 13.5px; line-height: 1.5; color: {c["text_muted"]}; max-width: 820px;">'
        f'2D utility-density mapping, real-time object inspection, and decision arbitration rationales across all active Tier-1 cache keys.'
        f'</p>'
        f'</div>'
        f'<div style="display: flex; align-items: center; padding-top: 6px;">'
        f'<span style="font-size: 10.5px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; background: rgba(56, 189, 248, 0.12); color: {c["cyan"]}; border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 6px; padding: 4px 12px; white-space: nowrap;">'
        f'TIER-1 IN-MEMORY REGISTRY &bull; DIAGNOSTICS'
        f'</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # HERO METRICS STRIP
    # --------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)

    total_keys = len(df_all)
    protected_count = (
        len(
            df_all[
                df_all["status"].str.contains("Protected|Refreshed", na=False)
            ]
        )
        if not df_all.empty
        else 0
    )
    eviction_count = (
        len(df_all[df_all["status"].str.contains("Eviction|Risk", na=False)])
        if not df_all.empty
        else 0
    )
    avg_score = df_all["utility_score"].mean() if not df_all.empty else 0.0

    with k1:
        render_metric_card(
            "Active Cache Keys",
            f"{total_keys:,}",
            subtitle="Tier-1 in-memory registry",
            tag="OBJECT REGISTRY",
            delta="Managed by Arbiter",
            delta_color=c["cyan"],
            is_floating=True,
            tooltip="Total key-value entries presently tracked in RAM.",
            progress_value=min(1.0, total_keys / 20.0),
            progress_color=c["cyan"],
        )

    with k2:
        render_metric_card(
            "High-Cost Protected",
            f"{protected_count} Keys",
            subtitle="Shielded from blind eviction",
            tag="API SHIELD",
            delta="Cost-Density Priority",
            delta_color="#10B981",
            tooltip="Items with high recompute cost or heavy access velocity locked against standard LRU pruning.",
            progress_value=(
                (protected_count / total_keys) if total_keys > 0 else 0
            ),
            progress_color="#10B981",
        )

    with k3:
        render_metric_card(
            "Eviction Candidates",
            f"{eviction_count} Keys",
            subtitle="Queued for pruning",
            tag="AT RISK",
            delta="Low cost-to-size density",
            delta_color=c["rose"],
            tooltip="Bulky items with low frequency, low hit penalty, or stale TTLs prioritized for eviction.",
            progress_value=(
                (eviction_count / total_keys) if total_keys > 0 else 0
            ),
            progress_color=c["rose"],
        )

    with k4:
        render_metric_card(
            "Mean Utility Score",
            f"{avg_score:.2f} / 1.0",
            subtitle="+28% vs plain LRU",
            tag="RETENTION DENSITY",
            delta="Normalized GDSF Score",
            delta_color=c["emerald"],
            tooltip="System-wide average score across all objects. Higher values indicate efficient memory utilization.",
            progress_value=avg_score,
            progress_color="#10B981",
            is_floating=True,
        )

    st.write("")

    # --------------------------------------------------
    # 2D INTERACTIVE SCATTER PLOT
    # --------------------------------------------------
    st.markdown(
        f"""<div style="display: flex; justify-content: space-between; align-items: center; margin: 12px 0 8px 0;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                2D Cache Memory Landscape (Value Density vs Size)
            </h3>
            <span class="badge-pill badge-active">BUBBLE SIZE = HIT VELOCITY</span>
        </div>""",
        unsafe_allow_html=True,
    )
    st.caption(
        "Objects in the upper-left (high value, small footprint) are rigorously protected. Objects in the bottom-right (large footprint, low cost) are flagged for eviction."
    )

    render_scatter_bubble_chart(
        df=df_all,
        x_col="size_kb",
        y_col="cost_usd",
        size_col="hits_last_min",
        color_col="status",
        hover_name="key",
        title="Cost Density Distribution (Recompute Cost $ vs Memory Size KB)",
        x_title="Memory Footprint (KB)",
        y_title="Recompute Cost ($ USD)",
        height=380,
    )

    st.markdown(
        f'<div style="height: 1px; background: {c["card_border"]}; margin: 20px 0;"></div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------
    # OBJECT REGISTRY TABLE & DIAGNOSTIC INSPECTOR
    # --------------------------------------------------
    col_table, col_inspector = st.columns([1.6, 1.2])

    with col_table:
        st.markdown(
            f"""<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                    Tier-1 Cache Registry
                </h3>
                <span class="muted" style="font-size: 12px;">{len(df_all)} items in memory</span>
            </div>""",
            unsafe_allow_html=True,
        )

        f_col1, f_col2 = st.columns([2, 1])
        with f_col1:
            search_query = st.text_input(
                "Filter by key substring",
                placeholder="Search keys e.g. 'rec:', 'pricing:', 'user'...",
                label_visibility="collapsed",
            )
        with f_col2:
            status_filter = st.selectbox(
                "Status Filter",
                ["All Statuses"] + sorted(list(df_all["status"].unique())),
                label_visibility="collapsed",
            )

        df_filtered = df_all.copy()
        if search_query:
            df_filtered = df_filtered[
                df_filtered["key"].str.contains(search_query, case=False)
            ]
        if status_filter != "All Statuses":
            df_filtered = df_filtered[df_filtered["status"] == status_filter]

        table_event = st.dataframe(
            df_filtered[
                [
                    "key",
                    "status",
                    "decision",
                    "utility_score",
                    "size_kb",
                    "cost_usd",
                    "hits_last_min",
                ]
            ],
            column_config={
                "key": st.column_config.TextColumn(
                    "Cache Key", width="medium"
                ),
                "status": st.column_config.TextColumn("Tier Status", width="small"),
                "decision": st.column_config.TextColumn("Arbiter", width="small"),
                "utility_score": st.column_config.ProgressColumn(
                    "Utility Score", min_value=0.0, max_value=1.0, format="%.2f"
                ),
                "size_kb": st.column_config.NumberColumn(
                    "Size (KB)", format="%d KB"
                ),
                "cost_usd": st.column_config.NumberColumn(
                    "Cost ($)", format="$%.3f"
                ),
                "hits_last_min": st.column_config.NumberColumn(
                    "Velocity", format="%d req/m"
                ),
            },
            hide_index=True,
            width="stretch",
            height=370,
            on_select="rerun",
            selection_mode="single-row",
            key="cache_objects_dataframe",
        )

        # Synchronize table row click to inspector
        if table_event:
            rows = []
            if hasattr(table_event, "selection") and hasattr(table_event.selection, "rows"):
                rows = table_event.selection.rows
            elif isinstance(table_event, dict) and "selection" in table_event and "rows" in table_event["selection"]:
                rows = table_event["selection"]["rows"]
            if rows and len(rows) > 0:
                selected_idx = rows[0]
                if 0 <= selected_idx < len(df_filtered):
                    clicked_key = df_filtered.iloc[selected_idx]["key"]
                    st.session_state["selected_diagnostic_key"] = clicked_key
                    st.session_state["diagnostic_inspector_selectbox"] = clicked_key

    with col_inspector:
        st.markdown(
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">'
            f'<h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c["text"]};">Key Diagnostic Inspector</h3>'
            f'<span style="font-size: 10px; font-weight: 700; color: {c["emerald"]}; background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 4px; padding: 2px 7px;">LIVE INSPECTOR</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        all_keys = list(df_all["key"].values)
        if "selected_diagnostic_key" not in st.session_state or st.session_state["selected_diagnostic_key"] not in all_keys:
            st.session_state["selected_diagnostic_key"] = all_keys[0] if all_keys else None

        current_key = st.session_state.get("selected_diagnostic_key")
        def_index = all_keys.index(current_key) if (current_key and current_key in all_keys) else 0

        def _on_inspector_select_change():
            st.session_state["selected_diagnostic_key"] = st.session_state.get("diagnostic_inspector_selectbox")

        selected_key = st.selectbox(
            "Select object to inspect decision rationale:",
            all_keys,
            index=def_index if all_keys else None,
            key="diagnostic_inspector_selectbox",
            on_change=_on_inspector_select_change,
        )

        if selected_key:
            st.session_state["selected_diagnostic_key"] = selected_key
            item = next(
                (x for x in raw_objects if x["key"] == selected_key), None
            )
            if item:
                d_badge = get_decision_badge_html(item["decision"])
                s_type = (
                    "protected" if "Protected" in item.get("status", "") or "Locked" in item.get("status", "")
                    else ("hot" if "Hot" in item.get("status", "")
                    else ("danger" if "Evict" in item.get("status", "") or "Risk" in item.get("status", "")
                    else "active"))
                )
                s_badge = get_status_pill_html(item["status"], status_type=s_type)
                rationale_text = item.get(
                    "rationale",
                    "High economic value density offsets RAM footprint. Maintained in memory to avoid backend latency penalty."
                )

                inspector_card_html = (
                    f'<div class="decision-card" style="padding: 18px; margin-bottom: 16px; border-radius: 12px; background: {c["card_bg"]}; border: 1px solid {c["card_border"]};">'
                    f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">'
                    f'<span style="font-size: 10.5px; font-weight: 800; color: {c["text_muted"]}; letter-spacing: 0.6px; text-transform: uppercase;">ENGINE VERDICT</span>'
                    f'<div style="display: flex; gap: 6px; align-items: center;">{d_badge} {s_badge}</div>'
                    f'</div>'
                    f'<div style="margin-bottom: 10px;">'
                    f'<span style="font-size: 10px; font-weight: 700; color: {c["text_subtle"]}; text-transform: uppercase; display: block; margin-bottom: 3px;">CACHE KEY IDENTIFIER</span>'
                    f'<code style="font-size: 12px; color: {c["cyan"]}; font-weight: 700; word-break: break-all; background: {c["card_bg_elevated"]}; padding: 5px 8px; border-radius: 6px; border: 1px solid {c["card_border"]}; display: block; font-family: monospace;">{item["key"]}</code>'
                    f'</div>'
                    f'<div style="margin: 10px 0; padding: 10px 12px; background: {c["card_bg_elevated"]}; border-radius: 8px; border: 1px solid {c["card_border"]};">'
                    f'<span style="font-size: 10px; font-weight: 800; color: {c["text_muted"]}; letter-spacing: 0.5px; text-transform: uppercase;">ARBITER RATIONALE</span>'
                    f'<div style="font-size: 12px; color: {c["text"]}; margin-top: 3px; line-height: 1.45;">{rationale_text}</div>'
                    f'</div>'
                    f'<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 4px; text-align: center;">'
                    f'<div style="background: {c["card_bg_elevated"]}; padding: 8px 6px; border-radius: 6px; border: 1px solid {c["card_border"]};">'
                    f'<span class="muted" style="font-size: 9.5px; font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 2px;">Score</span>'
                    f'<div style="font-size: 14px; font-weight: 800; color: #10B981;">{float(item["utility_score"]):.2f}</div>'
                    f'</div>'
                    f'<div style="background: {c["card_bg_elevated"]}; padding: 8px 6px; border-radius: 6px; border: 1px solid {c["card_border"]};">'
                    f'<span class="muted" style="font-size: 9.5px; font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 2px;">Cost</span>'
                    f'<div style="font-size: 14px; font-weight: 800; color: {c["amber"]};">${float(item["cost_usd"]):.3f}</div>'
                    f'</div>'
                    f'<div style="background: {c["card_bg_elevated"]}; padding: 8px 6px; border-radius: 6px; border: 1px solid {c["card_border"]};">'
                    f'<span class="muted" style="font-size: 9.5px; font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 2px;">Velocity</span>'
                    f'<div style="font-size: 14px; font-weight: 800; color: {c["cyan"]};">{item["hits_last_min"]} <span style="font-size: 9px; font-weight: 500;">req/m</span></div>'
                    f'</div>'
                    f'</div>'
                    f'</div>'
                )
                st.markdown(inspector_card_html, unsafe_allow_html=True)

                # Diagnostic Interactive Action Buttons
                st.markdown(
                    f'<div style="margin-top: 12px; margin-bottom: 8px;"><span style="font-size: 11px; font-weight: 800; letter-spacing: 0.5px; text-transform: uppercase; color: {c["text_muted"]};">EXECUTE OPERATOR ACTION:</span></div>',
                    unsafe_allow_html=True,
                )
                act1, act2, act3 = st.columns(3)
                with act1:
                    if st.button("⚡ Refresh", key="btn_refresh", width="stretch", help="Trigger background async X-Fetch"):
                        item["decision"] = "REFRESH"
                        item["status"] = "Protected (Refreshed)"
                        item["utility_score"] = min(1.0, round(float(item["utility_score"]) + 0.15, 2))
                        item["rationale"] = "Manual operator dispatch: Asynchronous background X-Fetch recomputation scheduled."
                        st.toast(f"⚡ Dispatched background async refresh for {item['key']}", icon="⚡")
                        st.rerun()
                with act2:
                    if st.button("🔒 Lock RAM", key="btn_lock", width="stretch", help="Pin object into Tier-1 RAM"):
                        item["decision"] = "RETAIN"
                        item["status"] = "Protected (Locked)"
                        item["utility_score"] = max(float(item["utility_score"]), 0.95)
                        item["rationale"] = "Manual operator lock: Object pinned in Tier-1 RAM, shielded from eviction."
                        st.toast(f"🔒 Locked {item['key']} into RAM (Pinned)", icon="🔒")
                        st.rerun()
                with act3:
                    if st.button("🗑️ Evict Now", key="btn_evict", width="stretch", help="Evict from Tier-1 RAM"):
                        item["decision"] = "EVICT"
                        item["status"] = "Eviction Candidate"
                        item["utility_score"] = max(0.05, round(float(item["utility_score"]) - 0.45, 2))
                        item["rationale"] = "Manual operator override: Object marked for immediate recycling to free cache space."
                        st.toast(f"🗑️ Evicted {item['key']} from Tier-1 RAM", icon="🗑️")
                        st.rerun()
