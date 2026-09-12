import html

import pandas as pd
import streamlit as st

from frontend.components.charts import render_scatter_bubble_chart
from frontend.components.metric_card import render_metric_card
from frontend.components.status_badge import (
    get_decision_badge_html,
    get_status_pill_html,
)
from frontend.components.styles import get_theme_colors
from frontend.services.api_client import api_client
from frontend.services.data_service import invalidate_cache_key
from frontend.services.telemetry_service import get_telemetry_observation
from frontend.utils.formatting import format_int

# Short TTL so the registry table/scatter/inspector share one backend round
# trip per rerun burst instead of re-fetching on every widget interaction.
_CACHE_OBJECTS_TTL_SECONDS = 2


@st.cache_data(ttl=_CACHE_OBJECTS_TTL_SECONDS, show_spinner=False)
def _get_cache_objects_cached() -> dict:
    return api_client.get_cache_objects()


def render_cache_objects_view():
    """Render Cache Objects & Memory Landscape with interactive 2D density chart and diagnostic inspector."""
    c = get_theme_colors()

    # Telemetry live keys observation
    obs = get_telemetry_observation()
    live_access_counts = obs.get("current_window_access_counts", {})

    # --------------------------------------------------
    # DATA RETRIEVAL (LIVE / FALLBACK)
    # --------------------------------------------------
    cache_response = _get_cache_objects_cached()
    is_live = cache_response.get("is_live", False)
    fetched_objects = [dict(item) for item in cache_response.get("objects", [])]
    raw_objects = []
    for item in fetched_objects:
        key = item.get("key", "")
        # Apply live telemetry window count if available
        if key in live_access_counts:
            item["hits_last_min"] = live_access_counts[key]
            item["access_count"] = max(item.get("access_count", 1), live_access_counts[key])
        else:
            item["hits_last_min"] = item.get("access_count", 1)

        # Map size in KB
        if "size_kb" not in item:
            size_b = item.get("size_bytes", 0)
            item["size_kb"] = max(0.1, round(size_b / 1024.0, 2))

        # Map retrieval cost to USD (frontend display heuristic)
        if "cost_usd" not in item:
            if "recompute_cost_usd" in item:
                item["cost_usd"] = float(item["recompute_cost_usd"])
            else:
                cost_ms = float(item.get("retrieval_cost_ms", 10.0))
                item["cost_usd"] = round(max(0.005, cost_ms * 0.001), 3)

        # Map status tier (frontend diagnostic heuristic)
        if "status" not in item:
            acc = item.get("access_count", 1)
            hits = item.get("hit_count", 0)
            cost_ms = item.get("retrieval_cost_ms", 0.0)
            if hits >= 3 or acc >= 5:
                item["status"] = "Protected (High Cost)" if cost_ms > 20 else "Hot"
            elif hits >= 1 or acc >= 2:
                item["status"] = "Active"
            else:
                item["status"] = "Active"

        # Map diagnostic action (frontend display heuristic)
        if "decision" not in item:
            item["decision"] = (
                "RETAIN"
                if ("Protected" in item.get("status", "") or "Hot" in item.get("status", "") or "Active" in item.get("status", ""))
                else "EVICT"
            )

        # Map utility score (frontend display heuristic)
        if "utility_score" not in item:
            acc = item.get("access_count", 1)
            cost_ms = item.get("retrieval_cost_ms", 0.0)
            norm_score = min(0.99, max(0.20, 0.35 + 0.10 * min(acc, 5) + 0.005 * min(cost_ms, 50.0)))
            item["utility_score"] = round(norm_score, 2)

        # Map diagnostic rationale (frontend heuristic explanation)
        if "rationale" not in item:
            if item["decision"] == "RETAIN":
                item["rationale"] = "Observed access velocity and retrieval penalty suggest caching benefit offsets RAM usage."
            elif item["decision"] == "REFRESH":
                item["rationale"] = "Background refresh heuristic: Object approaching expiration with active access patterns."
            else:
                item["rationale"] = "Low access frequency observed relative to memory footprint; heuristic flags for memory recycling under pressure."

        raw_objects.append(item)

    df_all = pd.DataFrame(raw_objects)

    # Header Title Block with cleanly aligned right badge
    tag_bg = "rgba(255, 255, 255, 0.06)" if c["is_dark"] else "rgba(0, 0, 0, 0.05)"
    header_html = (
        f'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin: 0 0 12px 0; flex-wrap: wrap; gap: 12px;">'
        f'<div>'
        f'<h1 style="margin: 0 0 6px 0; font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; color: {c["text"]} !important;">'
        f'Cache Objects & <span style="color: {c["text_muted"]} !important; font-weight: 600;">Memory Landscape</span>'
        f'</h1>'
        f'<p style="margin: 0; font-size: 13.5px; line-height: 1.5; color: {c["text_muted"]}; max-width: 820px;">'
        f'2D value-density mapping, real-time resident object inspection, and frontend-derived diagnostic indicators across active Tier-1 cache keys.'
        f'</p>'
        f'</div>'
        f'<div style="display: flex; align-items: center; padding-top: 6px;">'
        f'<span style="font-size: 10.5px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; background: {tag_bg}; color: {c["text_muted"]}; border: 1px solid {c["card_border"]}; border-radius: 6px; padding: 4px 12px; white-space: nowrap;">'
        f'TIER-1 IN-MEMORY REGISTRY &bull; DIAGNOSTICS'
        f'</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # INTEGRATION NOTICE (LIVE / FALLBACK)
    # --------------------------------------------------
    if is_live:
        notice_html = (
            f'<div class="hero-card" style="padding: 12px 18px; margin-bottom: 20px; border-left: 4px solid {c["emerald"]} !important;">'
            f'<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">'
            f'<div style="display: flex; align-items: center; gap: 8px;">'
            f'<span style="font-size: 14px;">🟢</span>'
            f'<strong style="font-size: 13px; color: {c["text"]};">Live Resident Cache Registry</strong>'
            f'</div>'
            f'<span class="badge-pill badge-active" style="font-size: 10px;">LIVE BACKEND &bull; GET /cache/objects</span>'
            f'</div>'
            f'<p style="font-size: 12px; color: {c["text_muted"]}; margin: 0; line-height: 1.5;">'
            f'Directly connected to FastAPI <code>GET /cache/objects</code>. '
            f'Observing {len(raw_objects)} currently resident cache {"entry" if len(raw_objects) == 1 else "entries"} with real-time metadata from CacheManager. '
            f'<span style="color: {c["text"]}; font-weight: 600;">Note:</span> Status tier, cost ($), and utility score are frontend-derived heuristics for memory visualization.'
            f'</p>'
            f'</div>'
        )
    else:
        notice_html = (
            f'<div class="hero-card" style="padding: 12px 18px; margin-bottom: 20px; border-left: 4px solid {c["amber"]} !important;">'
            f'<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">'
            f'<div style="display: flex; align-items: center; gap: 8px;">'
            f'<span style="font-size: 14px;">⚠️</span>'
            f'<strong style="font-size: 13px; color: {c["text"]};">Object Registry: Offline Fallback Data</strong>'
            f'</div>'
            f'<span class="badge-pill badge-hot" style="font-size: 10px;">DEMO / FALLBACK &bull; BACKEND OFFLINE</span>'
            f'</div>'
            f'<p style="font-size: 12px; color: {c["text_muted"]}; margin: 0; line-height: 1.5;">'
            f'FastAPI backend is unreachable at <code>{api_client.base_url}</code>. '
            f'Displaying schema demo fallback cache objects to illustrate the memory landscape architecture.'
            f'</p>'
            f'</div>'
        )
    st.markdown(notice_html, unsafe_allow_html=True)

    # Live Observed Keys in current telemetry window
    if live_access_counts:
        st.markdown(
            f"""<div style="margin-bottom: 12px; display:flex; justify-content:space-between; align-items:center;">
                <h4 style="margin: 0; font-size: 1rem; font-weight: 700; color: {c['text']};">
                    Live Keys Observed in Active Telemetry Window
                </h4>
                <span class="badge-pill badge-active" style="font-size: 10px;">GET /telemetry/observation</span>
            </div>""",
            unsafe_allow_html=True,
        )
        l_cols = st.columns(min(4, len(live_access_counts)))
        for idx, (lk, lcnt) in enumerate(sorted(live_access_counts.items(), key=lambda x: x[1], reverse=True)[:4]):
            with l_cols[idx % len(l_cols)]:
                st.markdown(
                    f"""
                    <div class="status-card" style="padding: 10px 12px;">
                        <span class="muted" style="font-size: 10px; font-weight: 700; text-transform: uppercase;">KEY</span>
                        <div style="font-family: monospace; font-size: 12px; font-weight: 700; color: {c['text']}; margin: 2px 0 4px 0;">{html.escape(str(lk))}</div>
                        <div style="font-size: 13px; font-weight: 800; color: {c['text']};">{format_int(lcnt)} accesses</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # --------------------------------------------------
    # HERO METRICS STRIP
    # --------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)

    total_keys = len(df_all)
    protected_count = (
        len(
            df_all[
                df_all["status"].str.contains("Protected", na=False)
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
            delta="Resident in RAM",
            delta_color=c["text_muted"],
            is_floating=True,
            tooltip="Total key-value entries presently resident in RAM.",
            progress_value=min(1.0, total_keys / 20.0),
            progress_color=c["emerald"],
        )

    with k2:
        render_metric_card(
            "High-Cost Protected",
            f"{protected_count} Keys",
            subtitle="Heuristic retention priority",
            tag="RETENTION SHIELD",
            delta="Diagnostic Heuristic",
            delta_color="#10B981",
            tooltip="Items with high recompute latency or heavy access velocity prioritized for retention.",
            progress_value=(
                (protected_count / total_keys) if total_keys > 0 else 0
            ),
            progress_color="#10B981",
        )

    with k3:
        render_metric_card(
            "Eviction Candidates",
            f"{eviction_count} Keys",
            subtitle="Heuristic pruning candidates",
            tag="LOW DENSITY",
            delta="Pruning Heuristic",
            delta_color=c["rose"],
            tooltip="Items with lower frequency or higher memory footprint flagged by heuristic as potential pruning targets.",
            progress_value=(
                (eviction_count / total_keys) if total_keys > 0 else 0
            ),
            progress_color=c["rose"],
        )

    with k4:
        render_metric_card(
            "Mean Utility Score",
            f"{avg_score:.2f} / 1.0",
            subtitle="Heuristic score average",
            tag="RETENTION DENSITY",
            delta="Frontend Heuristic",
            delta_color=c["emerald"],
            tooltip="Average frontend-derived utility score across resident objects based on size, latency, and access velocity.",
            progress_value=avg_score,
            progress_color="#10B981",
            is_floating=True,
        )

    # --------------------------------------------------
    # 2D INTERACTIVE SCATTER PLOT
    # --------------------------------------------------
    st.markdown(
        f"""<div style="display: flex; justify-content: space-between; align-items: center; margin: 28px 0 10px 0;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                2D Cache Memory Landscape (Value Density vs Size)
            </h3>
            <span class="badge-pill badge-active">BUBBLE SIZE = HIT VELOCITY</span>
        </div>""",
        unsafe_allow_html=True,
    )
    st.caption(
        "Objects in the upper-left (high value, small footprint) have higher retention density. Note: Recompute cost ($) and value density are frontend display heuristics."
    )

    if not df_all.empty:
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
    else:
        st.markdown(
            f'<div style="background: {c["card_bg"]}; border: 1px dashed {c["card_border"]}; border-radius: 10px; padding: 36px 20px; text-align: center; margin: 10px 0;">'
            f'<span style="font-size: 28px; display: block; margin-bottom: 8px;">📊</span>'
            f'<strong style="font-size: 14px; color: {c["text"]}; display: block; margin-bottom: 4px;">Memory Landscape Canvas Empty</strong>'
            f'<p style="font-size: 12.5px; color: {c["text_muted"]}; margin: 0; max-width: 500px; margin: 0 auto;">No resident cache entries currently stored. Send traffic via <strong>Request Simulator</strong> (GET /data/product/1 or GET /data/recommendation/1) to populate items and observe real-time positioning.</p>'
            f'</div>',
            unsafe_allow_html=True,
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
        table_badge_color = c["emerald"] if is_live else c["amber"]
        table_badge_text = "[LIVE BACKEND]" if is_live else "[DEMO FALLBACK]"
        st.markdown(
            f"""<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                    Tier-1 Cache Registry <span style="font-size: 11px; font-weight: 700; color: {table_badge_color};">{table_badge_text}</span>
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
            status_options = ["All Statuses"] + sorted(df_all["status"].unique()) if not df_all.empty else ["All Statuses"]
            status_filter = st.selectbox(
                "Status Filter",
                status_options,
                label_visibility="collapsed",
            )

        df_filtered = df_all.copy()
        if not df_filtered.empty:
            if search_query:
                # regex=False: treat the query as a literal substring so an
                # unbalanced/invalid regex (e.g. a stray "(") typed by a user
                # can't raise and crash the page.
                df_filtered = df_filtered[
                    df_filtered["key"].str.contains(
                        search_query, case=False, regex=False
                    )
                ]
            if status_filter != "All Statuses":
                df_filtered = df_filtered[df_filtered["status"] == status_filter]

        if not df_filtered.empty:
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
                    "status": st.column_config.TextColumn("Diagnostic Tier", width="small"),
                    "decision": st.column_config.TextColumn("Diagnostic Action*", width="small"),
                    "utility_score": st.column_config.ProgressColumn(
                        "Utility Score*", min_value=0.0, max_value=1.0, format="%.2f"
                    ),
                    "size_kb": st.column_config.NumberColumn(
                        "Size (KB)", format="%.1f KB"
                    ),
                    "cost_usd": st.column_config.NumberColumn(
                        "Est. Cost ($)*", format="$%.3f"
                    ),
                    "hits_last_min": st.column_config.NumberColumn(
                        "Velocity", format="%d req"
                    ),
                },
                hide_index=True,
                width="stretch",
                height=370,
                on_select="rerun",
                selection_mode="single-row",
                key="cache_objects_dataframe",
            )
            st.caption("* Diagnostic Action, Utility Score, and Est. Cost are frontend-derived heuristics for memory visualization. Live engine decisions are computed via the Adaptive Decisions page.")

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
        else:
            st.info("No cache entries match the current filter or cache is empty.")

    with col_inspector:
        insp_color = c["emerald"] if is_live else c["amber"]
        insp_bg = "rgba(16, 185, 129, 0.12)" if is_live else "rgba(245, 158, 11, 0.12)"
        insp_border = "rgba(16, 185, 129, 0.25)" if is_live else "rgba(245, 158, 11, 0.25)"
        insp_badge = "LIVE INSPECTOR" if is_live else "DEMO INSPECTOR"

        st.markdown(
            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">'
            f'<h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c["text"]};">Key Diagnostic Inspector</h3>'
            f'<span style="font-size: 10px; font-weight: 700; color: {insp_color}; background: {insp_bg}; border: 1px solid {insp_border}; border-radius: 4px; padding: 2px 7px;">{insp_badge}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        all_keys = list(df_all["key"].values) if not df_all.empty else []
        if not all_keys:
            st.caption("No resident keys available to inspect.")
        else:
            if "selected_diagnostic_key" not in st.session_state or st.session_state["selected_diagnostic_key"] not in all_keys:
                st.session_state["selected_diagnostic_key"] = all_keys[0]

            current_key = st.session_state.get("selected_diagnostic_key")
            def_index = all_keys.index(current_key) if (current_key and current_key in all_keys) else 0

            def _on_inspector_select_change():
                st.session_state["selected_diagnostic_key"] = st.session_state.get("diagnostic_inspector_selectbox")

            selected_key = st.selectbox(
                "Select object to inspect diagnostic rationale:",
                all_keys,
                index=def_index,
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
                        "protected" if "Protected" in item.get("status", "")
                        else ("hot" if "Hot" in item.get("status", "")
                        else ("danger" if "Evict" in item.get("status", "") or "Risk" in item.get("status", "")
                        else "active"))
                    )
                    s_badge = get_status_pill_html(item["status"], status_type=s_type)
                    rationale_text = item.get(
                        "rationale",
                        "Observed access velocity and retrieval penalty suggest caching benefit offsets RAM usage."
                    )

                    inspector_card_html = (
                        f'<div class="decision-card" style="padding: 20px 22px; margin-bottom: 20px; border-radius: 12px; background: {c["card_bg"]}; border: 1px solid {c["card_border"]};">'
                        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">'
                        f'<span style="font-size: 10.5px; font-weight: 800; color: {c["text_muted"]}; letter-spacing: 0.6px; text-transform: uppercase;">CACHE DIAGNOSTIC</span>'
                        f'<div style="display: flex; gap: 6px; align-items: center;">{d_badge} {s_badge}</div>'
                        f'</div>'
                        f'<div style="margin-bottom: 12px;">'
                        f'<span style="font-size: 10px; font-weight: 700; color: {c["text_subtle"]}; text-transform: uppercase; display: block; margin-bottom: 4px;">CACHE KEY IDENTIFIER</span>'
                        f'<code style="font-size: 12px; color: {c["text"]}; font-weight: 700; word-break: break-all; background: {c["card_bg_elevated"]}; padding: 6px 10px; border-radius: 6px; border: 1px solid {c["card_border"]}; display: block; font-family: monospace;">{html.escape(str(item["key"]))}</code>'
                        f'</div>'
                        f'<div style="margin: 12px 0; padding: 12px 14px; background: {c["card_bg_elevated"]}; border-radius: 8px; border: 1px solid {c["card_border"]};">'
                        f'<span style="font-size: 10px; font-weight: 800; color: {c["text_muted"]}; letter-spacing: 0.5px; text-transform: uppercase;">DERIVED INSIGHT</span>'
                        f'<div style="font-size: 12px; color: {c["text"]}; margin-top: 4px; line-height: 1.5;">{html.escape(str(rationale_text))}</div>'
                        f'<span style="font-size: 9.5px; color: {c["text_muted"]}; display: block; margin-top: 6px; font-style: italic;">* Frontend-derived heuristic based on observed access counts, size, and retrieval latency. Not an AEGIS DecisionEngine output.</span>'
                        f'</div>'
                        f'<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 10px; text-align: center;">'
                        f'<div style="background: {c["card_bg_elevated"]}; padding: 10px 8px; border-radius: 8px; border: 1px solid {c["card_border"]};">'
                        f'<span class="muted" style="font-size: 9.5px; font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 2px;">Score*</span>'
                        f'<div style="font-size: 15px; font-weight: 800; color: {c["emerald"]};">{float(item["utility_score"]):.2f}</div>'
                        f'</div>'
                        f'<div style="background: {c["card_bg_elevated"]}; padding: 10px 8px; border-radius: 8px; border: 1px solid {c["card_border"]};">'
                        f'<span class="muted" style="font-size: 9.5px; font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 2px;">Cost*</span>'
                        f'<div style="font-size: 15px; font-weight: 800; color: {c["amber"]};">${float(item["cost_usd"]):.3f}</div>'
                        f'</div>'
                        f'<div style="background: {c["card_bg_elevated"]}; padding: 10px 8px; border-radius: 8px; border: 1px solid {c["card_border"]};">'
                        f'<span class="muted" style="font-size: 9.5px; font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 2px;">Velocity</span>'
                        f'<div style="font-size: 15px; font-weight: 800; color: {c["text"]};">{item["hits_last_min"]} <span style="font-size: 9.5px; font-weight: 500;">req</span></div>'
                        f'</div>'
                        f'</div>'
                        f'<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 8px; text-align: center;">'
                        f'<div style="background: {c["card_bg_elevated"]}; padding: 8px 6px; border-radius: 8px; border: 1px solid {c["card_border"]};">'
                        f'<span class="muted" style="font-size: 9px; font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 2px;">Hits / Misses</span>'
                        f'<div style="font-size: 12px; font-weight: 700; color: {c["text"]};">{item.get("hit_count", 0)} / {item.get("miss_count", 0)}</div>'
                        f'</div>'
                        f'<div style="background: {c["card_bg_elevated"]}; padding: 8px 6px; border-radius: 8px; border: 1px solid {c["card_border"]};">'
                        f'<span class="muted" style="font-size: 9px; font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 2px;">Size</span>'
                        f'<div style="font-size: 12px; font-weight: 700; color: {c["text"]};">{item.get("size_bytes", int(item.get("size_kb", 1) * 1024)):,} B</div>'
                        f'</div>'
                        f'<div style="background: {c["card_bg_elevated"]}; padding: 8px 6px; border-radius: 8px; border: 1px solid {c["card_border"]};">'
                        f'<span class="muted" style="font-size: 9px; font-weight: 700; text-transform: uppercase; display: block; margin-bottom: 2px;">Latency</span>'
                        f'<div style="font-size: 12px; font-weight: 700; color: {c["text"]};">{float(item.get("retrieval_cost_ms", 0.0)):.1f} ms</div>'
                        f'</div>'
                        f'</div>'
                        f'</div>'
                    )
                    st.markdown(inspector_card_html, unsafe_allow_html=True)

                    if is_live:
                        inv_col1, inv_col2 = st.columns([2, 1])
                        with inv_col1:
                            st.caption(
                                "Manually evict this object from Tier-1 RAM and its persisted metadata."
                            )
                        with inv_col2:
                            if st.button(
                                "🗑️ Invalidate",
                                key=f"invalidate_{selected_key}",
                                width="stretch",
                                help="DELETE /cache/objects/{key} — removes this entry now.",
                            ):
                                inv_result = invalidate_cache_key(selected_key)
                                _get_cache_objects_cached.clear()
                                if inv_result.get("deleted"):
                                    st.toast(
                                        f"Invalidated '{selected_key}'", icon="🗑️"
                                    )
                                elif inv_result.get("is_live"):
                                    st.toast(
                                        f"'{selected_key}' was already gone",
                                        icon="ℹ️",
                                    )
                                else:
                                    st.toast(
                                        "Backend unreachable — nothing invalidated",
                                        icon="⚠️",
                                    )
                                st.session_state.pop("selected_diagnostic_key", None)
                                st.rerun()
                    else:
                        st.caption(
                            "Manual invalidation requires a live backend connection."
                        )
