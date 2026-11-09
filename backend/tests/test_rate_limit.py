"""Unit tests for the in-process sliding-window rate limiter, eviction, and Retry-After headers."""

import time
import pytest
from api.middleware.rate_limit import (
    Decision,
    InMemorySlidingWindowLimiter,
    RateLimitRule,
)


def test_sliding_window_allows_under_limit():
    """Requests under maximum limit should be allowed with correct remaining balance."""
    limiter = InMemorySlidingWindowLimiter()
    rule = RateLimitRule(max_requests=3, window_seconds=60)
    key = "test_key_1"

    d1 = limiter.check(key, rule)
    assert d1.allowed is True
    assert d1.remaining == 2
    assert d1.retry_after_seconds == 0

    d2 = limiter.check(key, rule)
    assert d2.allowed is True
    assert d2.remaining == 1

    d3 = limiter.check(key, rule)
    assert d3.allowed is True
    assert d3.remaining == 0


def test_sliding_window_blocks_and_calculates_retry_after():
    """Requests exceeding maximum limit should be rejected with a positive retry_after_seconds."""
    limiter = InMemorySlidingWindowLimiter()
    rule = RateLimitRule(max_requests=2, window_seconds=10)
    key = "test_key_2"

    limiter.check(key, rule)
    limiter.check(key, rule)

    # 3rd request should fail
    d3 = limiter.check(key, rule)
    assert d3.allowed is False
    assert d3.retry_after_seconds > 0
    assert d3.retry_after_seconds <= 10
    assert d3.remaining == 0


def test_sliding_window_bounded_memory_eviction():
    """Limiter with a small max_keys cap must safely evict idle keys without unbounded growth."""
    limiter = InMemorySlidingWindowLimiter(max_keys=5)
    rule = RateLimitRule(max_requests=10, window_seconds=1)

    for i in range(15):
        limiter.check(f"user_{i}", rule)

    # Hard cap of keys should not exceed max_keys + margin
    assert len(limiter._store) <= 10
