import streamlit as st
from frontend.mocks.data import (
    cache_stats,
    cache_objects,
    workload,
    adaptive_decision,
    benchmark_results,
    performance_history,
)


@st.cache_data(ttl=300)
def get_cache_stats():
    return cache_stats


@st.cache_data(ttl=300)
def get_cache_objects():
    return [dict(item) for item in cache_objects]


@st.cache_data(ttl=300)
def get_workload():
    return workload


@st.cache_data(ttl=300)
def get_adaptive_decision():
    return adaptive_decision


@st.cache_data(ttl=300)
def get_benchmark_results():
    return benchmark_results


@st.cache_data(ttl=300)
def get_performance_history():
    return performance_history