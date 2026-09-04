from frontend.mocks.data import (
    cache_stats,
    cache_objects,
    workload,
    adaptive_decision,
    benchmark_results,
    performance_history,
)


def get_cache_stats():
    return cache_stats


def get_cache_objects():
    return cache_objects


def get_workload():
    return workload


def get_adaptive_decision():
    return adaptive_decision


def get_benchmark_results():
    return benchmark_results

def get_performance_history():
    return performance_history