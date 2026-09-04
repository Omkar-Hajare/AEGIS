import streamlit as st
import pandas as pd

from frontend.services.api_client import get_benchmark_results
from frontend.components.styles import get_theme_colors
from frontend.components.metric_card import render_metric_card
from frontend.components.charts import render_comparison_bar_chart


def render_benchmarks_view():
    """Render Policy Benchmarks & Empirical Evaluation with 4-quadrant algorithm comparison charts and matrix."""
    c = get_theme_colors()

    # Header Title Block with cleanly aligned right badge
    header_html = (
        f'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin: 0 0 12px 0; flex-wrap: wrap; gap: 12px;">'
        f'<div>'
        f'<h1 style="margin: 0 0 6px 0; font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; color: {c["text"]} !important;">'
        f'Policy Benchmarks & <span style="color: {c["text_muted"]} !important; font-weight: 600;">Empirical Evaluation</span>'
        f'</h1>'
        f'<p style="margin: 0; font-size: 13.5px; line-height: 1.5; color: {c["text_muted"]}; max-width: 820px;">'
        f'Rigorous empirical head-to-head evaluation of the Adaptive Engine (VH26 Satyagrah) against standard industry eviction algorithms (FIFO, LRU, LFU, GDSF).'
        f'</p>'
        f'</div>'
        f'<div style="display: flex; align-items: center; padding-top: 6px;">'
        f'<span style="font-size: 10.5px; font-weight: 800; letter-spacing: 0.8px; text-transform: uppercase; background: {"rgba(255, 255, 255, 0.06)" if c["is_dark"] else "rgba(0, 0, 0, 0.05)"}; color: {c["text_muted"]}; border: 1px solid {c["card_border"]}; border-radius: 6px; padding: 4px 12px; white-space: nowrap;">'
        f'EMPIRICAL COMPARISON &bull; 4-QUADRANT EVALUATION'
        f'</span>'
        f'</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # Fetch Benchmark Data
    benchmarks = get_benchmark_results()
    df = pd.DataFrame(benchmarks)
    policies = list(df["policy"])

    # --------------------------------------------------
    # BENCHMARK DATASET SOURCE CARD (MANDATORY SPEC RULE)
    # --------------------------------------------------
    source_html = (
        f'<div class="hero-card" style="padding: 10px 16px; margin-bottom: 16px; border: 1px solid {c["card_border"]} !important; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">'
        f'<div style="display: flex; align-items: center; gap: 8px;">'
        f'<span style="font-size: 13px;">📁</span>'
        f'<span style="font-size: 11.5px; font-weight: 700; color: {c["text_muted"]}; text-transform: uppercase;">BENCHMARK SUITE:</span>'
        f'<span style="font-size: 12px; font-weight: 700; color: {c["text"]};">Controlled Empirical Trace Evaluation (100k Operations, Zipfian s=1.15, k6 Harness)</span>'
        f'</div>'
        f'<span class="badge-pill badge-active" style="font-size: 10px;">OFFLINE REPLAY DATASET</span>'
        f'</div>'
    )
    st.markdown(source_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # EXECUTIVE SUMMARY RIBBON
    # --------------------------------------------------
    exec_ribbon_html = (
        f'<div class="hero-card" style="padding: 12px 18px; margin-bottom: 18px; border: 1px solid {c["card_border"]} !important; border-left: 3px solid {c["emerald"]} !important; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 16px rgba(0,0,0,0.12);">'
        f'<div style="display: flex; align-items: center; gap: 12px;">'
        f'<span class="badge-pill badge-protected" style="font-size: 11px; padding: 4px 10px;">★ LEADERBOARD WINNER</span>'
        f'<span style="font-size: 13.5px; font-weight: 800; color: {c["text"]};">Adaptive Multi-Factor Engine achieves superior Pareto frontier across all 4 production benchmarks</span>'
        f'</div>'
        f'<div style="font-size: 12px; color: {c["emerald"]}; font-weight: 700;">+11.2% Hit Rate &bull; -35.7% Latency &bull; -$7.20/hr Cloud Spend</div>'
        f'</div>'
    )
    st.markdown(exec_ribbon_html, unsafe_allow_html=True)

    # --------------------------------------------------
    # HERO VALUE METRICS STRIP
    # --------------------------------------------------
    m1, m2, m3, m4 = st.columns(4)

    with m1:
        render_metric_card(
            title="Peak Hit Rate",
            value="89.6%",
            subtitle="Adaptive Engine vs 78.4% LRU",
            tag="HIT RATE LEADER",
            delta="↑ +11.2% Gain",
            delta_color=c["emerald"],
            tooltip="Highest sustained cache hit rate under production Zipfian access patterns.",
            progress_value=0.896,
            progress_color=c["emerald"],
            is_floating=True,
        )

    with m2:
        render_metric_card(
            title="P95 Latency Winner",
            value="27.3 ms",
            subtitle="vs 42.5 ms on standard LRU",
            tag="LATENCY CHAMPION",
            delta="↓ -35.7% Speedup",
            delta_color=c["emerald"],
            tooltip="95th percentile read latency across 100,000 synthetic test operations.",
            progress_value=0.73,
            progress_color=c["emerald"],
        )

    with m3:
        render_metric_card(
            title="Hourly Cost Reduction",
            value="$11.20",
            subtitle="vs $18.40 on standard LRU",
            tag="CLOUD SPEND SAVINGS",
            delta="-$7.20 / hour Saved",
            delta_color=c["emerald"],
            tooltip="Calculated cloud backend database compute and third-party API spend.",
            progress_value=0.61,
            progress_color=c["emerald"],
            is_floating=True,
        )

    with m4:
        render_metric_card(
            title="Eviction Thrash Rate",
            value="2.1%",
            subtitle="vs 14.5% on standard LRU",
            tag="MEMORY STABILITY",
            delta="7× Churn Reduction",
            delta_color=c["purple"],
            tooltip="Percentage of prematurely evicted items requested again within 60 seconds.",
            progress_value=0.92,
            progress_color=c["purple"],
        )

    # --------------------------------------------------
    # 4-QUADRANT BENCHMARK COMPARISON CHARTS
    # --------------------------------------------------
    st.markdown(
        f"""<div style="margin: 32px 0 14px 0;">
            <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: {c['text']};">
                Heuristic Performance Comparison (4-Quadrant Benchmark)
            </h3>
        </div>""",
        unsafe_allow_html=True,
    )

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        render_comparison_bar_chart(
            categories=policies,
            values_dict={"Hit Rate (%)": list(df["hit_rate"])},
            title="Cache Hit Rate by Policy (%) [Higher is Better]",
            y_title="Hit Rate (%)",
            unit="%",
            height=290,
        )

    with col_chart2:
        render_comparison_bar_chart(
            categories=policies,
            values_dict={"P95 Latency (ms)": list(df["p95_latency_ms"])},
            title="P95 Read Latency by Policy (ms) [Lower is Better]",
            y_title="Latency (ms)",
            unit=" ms",
            height=290,
        )

    col_chart3, col_chart4 = st.columns(2)

    with col_chart3:
        render_comparison_bar_chart(
            categories=policies,
            values_dict={"Cost / Hr ($)": list(df["cost"])},
            title="Simulated Infrastructure Spend ($/hr) [Lower is Better]",
            y_title="Hourly Spend ($)",
            unit=" $",
            height=290,
        )

    with col_chart4:
        render_comparison_bar_chart(
            categories=policies,
            values_dict={"Thrash Rate (%)": list(df["eviction_thrash_rate"])},
            title="Eviction Thrashing Rate (%) [Lower is Better]",
            y_title="Thrash Rate (%)",
            unit="%",
            height=290,
        )

    st.markdown(
        f'<div style="height: 1px; background: {c["card_border"]}; margin: 32px 0 20px 0;"></div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------
    # EMPIRICAL RESULTS MATRIX TABLE
    # --------------------------------------------------
    st.markdown("### Empirical Benchmark Evaluation Matrix")

    display_df = df.copy()
    display_df["Hit Rate"] = display_df["hit_rate"].apply(lambda h: f"{h:.1f}%")
    display_df["P95 Latency"] = display_df["p95_latency_ms"].apply(
        lambda l: f"{l:.1f} ms"
    )
    display_df["Hourly Cost"] = display_df["cost"].apply(lambda c: f"${c:.2f}")
    display_df["Backend Miss Calls"] = display_df["backend_calls"].apply(
        lambda b: f"{b:,} calls"
    )

    st.dataframe(
        display_df[
            [
                "policy",
                "Hit Rate",
                "P95 Latency",
                "Hourly Cost",
                "Backend Miss Calls",
                "eviction_thrash_rate",
            ]
        ],
        column_config={
            "policy": st.column_config.TextColumn(
                "Algorithm Policy", width="medium"
            ),
            "Hit Rate": st.column_config.TextColumn(
                "Hit Rate (%)", width="small"
            ),
            "P95 Latency": st.column_config.TextColumn(
                "P95 Latency", width="small"
            ),
            "Hourly Cost": st.column_config.TextColumn(
                "Hourly Cost", width="small"
            ),
            "Backend Miss Calls": st.column_config.TextColumn(
                "Backend Offload", width="small"
            ),
            "eviction_thrash_rate": st.column_config.TextColumn(
                "Eviction Churn", width="small"
            ),
        },
        hide_index=True,
        width="stretch",
    )
