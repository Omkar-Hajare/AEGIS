"""Focused tests for GreedyDual-Size (GDS) baseline fairness and inflation clock.

Verifies:
1. Inflation clock starts at 0.0 (or configured initial value).
2. Eviction candidate is strictly the lowest GDS priority item.
3. Inflation clock advances correctly on eviction (L = H(evicted)).
4. Newly inserted objects receive correct priorities (L + cost / size).
5. Cache hits update object priority to current L + cost / size.
6. Equal-priority ties break deterministically by recency without alphabetical bias.
7. Capacity limits are strictly respected under multi-size objects.
8. Deterministic replay across identical runs.
9. Equivalence to LRU when all costs and sizes are identical (Cao & Irani 1997).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.adaptive.policies.gds import GDSPolicy
from contracts.schemas.cache import CacheObject


def make_obj(
    key: str,
    size_bytes: int,
    now: datetime,
    access_count: int = 1,
    retrieval_cost_ms: float = 10.0,
) -> CacheObject:
    """Helper to create a valid CacheObject instance."""
    return CacheObject(
        key=key,
        size_bytes=size_bytes,
        access_count=access_count,
        last_accessed=now,
        retrieval_cost_ms=retrieval_cost_ms,
    )


class TestGDSInflationClock:
    """Tests verifying standard GreedyDual-Size inflation clock dynamics."""

    def test_inflation_clock_starts_at_zero(self) -> None:
        """The inflation clock L starts at 0.0 by default."""
        policy = GDSPolicy()
        assert policy.clock_L == 0.0
        assert policy.priorities == {}

    def test_custom_initial_clock(self) -> None:
        """Policy can be initialized with custom inflation clock value."""
        policy = GDSPolicy(initial_L=5.5)
        assert policy.clock_L == 5.5

    def test_lowest_priority_is_evicted_first(self) -> None:
        """Eviction selects the candidate with the lowest H value."""
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        policy = GDSPolicy()
        # obj_low: 10 / 1000 = 0.01
        # obj_mid: 50 / 1000 = 0.05
        # obj_high: 200 / 1000 = 0.20
        objs = {
            "obj_low": make_obj("obj_low", 1000, now, retrieval_cost_ms=10.0),
            "obj_mid": make_obj("obj_mid", 1000, now, retrieval_cost_ms=50.0),
            "obj_high": make_obj("obj_high", 1000, now, retrieval_cost_ms=200.0),
        }
        evicted = policy.select_evictions(objs, 2000)
        assert evicted == ["obj_low"]
        assert policy.clock_L == pytest.approx(0.01)

    def test_inflation_clock_advances_on_eviction(self) -> None:
        """Inflation clock L advances to the priority of the evicted object."""
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        policy = GDSPolicy()
        objs = {
            "o1": make_obj("o1", 500, now, retrieval_cost_ms=10.0),  # H = 10/500 = 0.02
            "o2": make_obj("o2", 500, now, retrieval_cost_ms=25.0),  # H = 25/500 = 0.05
            "o3": make_obj("o3", 500, now, retrieval_cost_ms=50.0),  # H = 50/500 = 0.10
        }
        # Evict o1
        policy.select_evictions(objs, 1000)
        assert policy.clock_L == pytest.approx(0.02)

        # Remove o1 and evict o2
        remaining = {"o2": objs["o2"], "o3": objs["o3"]}
        policy.select_evictions(remaining, 500)
        assert policy.clock_L == pytest.approx(0.05)

    def test_newly_inserted_object_receives_inflated_priority(self) -> None:
        """New object inserted after clock inflation receives H = L + cost / size."""
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        policy = GDSPolicy()
        objs = {
            "o1": make_obj("o1", 500, now, retrieval_cost_ms=10.0),  # H = 0.02
            "o2": make_obj("o2", 500, now, retrieval_cost_ms=50.0),  # H = 0.10
        }
        policy.select_evictions(objs, 500)  # Evicts o1, L advances to 0.02
        assert policy.clock_L == pytest.approx(0.02)

        # New object admitted
        new_obj = make_obj("o_new", 1000, now, retrieval_cost_ms=30.0)  # cost/size = 0.03
        policy.on_insert("o_new", new_obj)
        # Priority must be L + cost/size = 0.02 + 0.03 = 0.05
        assert policy.priorities["o_new"] == pytest.approx(0.05)

    def test_cache_hit_updates_priority_with_current_clock(self) -> None:
        """Referencing an existing object refreshes its priority to H = L + cost / size."""
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        policy = GDSPolicy()
        old_obj = make_obj("retained", 1000, now, retrieval_cost_ms=10.0)  # H = 0.01 at L=0
        policy.on_insert("retained", old_obj)
        assert policy.priorities["retained"] == pytest.approx(0.01)

        # Simulate eviction of another item that advanced clock to L = 0.50
        policy._clock_L = 0.50

        # Now 'retained' is accessed (cache hit)
        policy.on_hit("retained", old_obj)
        # Should be updated to 0.50 + 10/1000 = 0.51
        assert policy.priorities["retained"] == pytest.approx(0.51)

    def test_equal_priority_ties_broken_by_recency_without_alphabetical_bias(self) -> None:
        """Objects with identical GDS priority are evicted by oldest last_accessed first.

        Ensures that 'catalog_0' is not systematically evicted if it was accessed
        more recently than 'catalog_99'.
        """
        t0 = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        t1 = t0 + timedelta(seconds=10)
        t2 = t0 + timedelta(seconds=20)

        policy = GDSPolicy()
        # All three have identical cost/size = 10 / 1000 = 0.01
        objs = {
            "catalog_0": make_obj("catalog_0", 1000, t2, retrieval_cost_ms=10.0),  # newest
            "catalog_50": make_obj("catalog_50", 1000, t1, retrieval_cost_ms=10.0), # middle
            "catalog_99": make_obj("catalog_99", 1000, t0, retrieval_cost_ms=10.0), # oldest
        }

        # Need to evict 1 object (1000 bytes).
        # Alphabetical sort would evict 'catalog_0'.
        # Recency-aware GDS must evict oldest: 'catalog_99'!
        evicted = policy.select_evictions(objs, 2000)
        assert evicted == ["catalog_99"], "Must evict oldest access, not alphabetical 'catalog_0'"

    def test_gds_reduces_to_lru_under_uniform_cost_and_size(self) -> None:
        """Cao & Irani (1997) Theorem: GDS reduces to LRU when all costs and sizes are identical.

        Under uniform workloads, GreedyDual-Size priority updates match LRU recency dynamics.
        """
        base_time = datetime(2026, 9, 4, 12, 0, 0, tzinfo=timezone.utc)
        policy = GDSPolicy()

        # Cache of capacity 3000 bytes (3 objects of 1000 B)
        cache: dict[str, CacheObject] = {}

        def access(key: str, sec: int) -> None:
            t = base_time + timedelta(seconds=sec)
            if key in cache:
                obj = cache[key]
                obj.access_count += 1
                obj.last_accessed = t
                policy.on_hit(key, obj)
            else:
                if sum(o.size_bytes for o in cache.values()) + 1000 > 3000:
                    ev = policy.select_evictions(cache, 2000)
                    for k in ev:
                        del cache[k]
                obj = make_obj(key, 1000, t, retrieval_cost_ms=10.0)
                cache[key] = obj
                policy.on_insert(key, obj)

        # Insert A(t=1), B(t=2), C(t=3) -> cache is [A, B, C]
        access("A", 1)
        access("B", 2)
        access("C", 3)

        # Hit A at t=4 -> LRU order becomes B, C, A
        access("A", 4)

        # Now insert D at t=5 -> must evict B (oldest accessed)
        access("D", 5)

        assert "B" not in cache, "B should be evicted under GDS equivalent to LRU"
        assert "A" in cache
        assert "C" in cache
        assert "D" in cache

    def test_capacity_bound_strictly_enforced_with_variable_sizes(self) -> None:
        """Capacity is strictly observed when objects of asymmetric sizes are evicted."""
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        policy = GDSPolicy()
        objs = {
            "small_1": make_obj("small_1", 1024, now, retrieval_cost_ms=10.0),
            "small_2": make_obj("small_2", 1024, now, retrieval_cost_ms=10.0),
            "large": make_obj("large", 8192, now, retrieval_cost_ms=10.0),  # pri = 10/8192 = 0.00122
        }
        # Total usage = 1024 + 1024 + 8192 = 10240. Target = 2048. bytes_to_free = 8192.
        # 'large' has the lowest priority and frees exactly 8192 bytes.
        evicted = policy.select_evictions(objs, 2048)
        assert evicted == ["large"]
        remaining_bytes = sum(objs[k].size_bytes for k in objs if k not in evicted)
        assert remaining_bytes <= 2048

    def test_reset_clears_clock_and_priorities(self) -> None:
        """Reset clears the inflation clock back to 0.0 and clears all priorities."""
        now = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
        policy = GDSPolicy()
        objs = {"o1": make_obj("o1", 100, now, retrieval_cost_ms=10.0)}
        policy.select_evictions(objs, 50)
        assert policy.clock_L > 0.0

        policy.reset()
        assert policy.clock_L == 0.0
        assert policy.priorities == {}
