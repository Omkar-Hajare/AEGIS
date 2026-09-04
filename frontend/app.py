import streamlit as st

from frontend.components.styles import apply_global_styles
from frontend.components.navbar import render_top_navbar, NAV_OPTIONS
from frontend.views.overview_view import render_overview_view
from frontend.views.cache_performance_view import render_cache_performance_view
from frontend.views.request_simulator_view import render_request_simulator_view
from frontend.views.workload_view import render_workload_view
from frontend.views.system_view import render_system_view
from frontend.views.cache_objects_view import render_cache_objects_view
from frontend.views.adaptive_decisions_view import render_adaptive_decisions_view
from frontend.views.cost_analysis_view import render_cost_analysis_view
from frontend.views.benchmarks_view import render_benchmarks_view

st.set_page_config(
    page_title="Adaptive Cache Control Center - Satyagrah",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Apply Cyber Obsidian Dark or Clean Off-White Light theme
apply_global_styles()

# Ensure active navigation state exists
if "active_nav" not in st.session_state:
    st.session_state["active_nav"] = "Overview"

# Render Persistent Modern Top Navigation Bar
active_tab = render_top_navbar(
    current_tab=st.session_state.get("active_nav", "Overview")
)

# --------------------------------------------------
# INSTANT ZERO-LAG IN-MEMORY VIEW ROUTER (9 MODULES)
# --------------------------------------------------
if active_tab in ("Overview", "Executive Overview"):
    render_overview_view()
elif active_tab in ("Performance", "Cache Performance"):
    render_cache_performance_view()
elif active_tab in ("Simulator", "Request Simulator"):
    render_request_simulator_view()
elif active_tab in ("Workload", "Workload Simulator"):
    render_workload_view()
elif active_tab in ("System", "System State"):
    render_system_view()
elif active_tab == "Cache Objects":
    render_cache_objects_view()
elif active_tab in ("Decisions", "Adaptive Decisions"):
    render_adaptive_decisions_view()
elif active_tab == "Cost Analysis":
    render_cost_analysis_view()
elif active_tab in ("Benchmarks", "Policy Benchmarks"):
    render_benchmarks_view()
else:
    render_overview_view()