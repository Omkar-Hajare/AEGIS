"""Baseline cache eviction policies for benchmarking."""

from .gds import GDSPolicy
from .lfu import LFUPolicy
from .lru import LRUPolicy

__all__ = ["LRUPolicy", "LFUPolicy", "GDSPolicy"]
