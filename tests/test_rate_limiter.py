"""Tests for engram/miner/rate_limiter.py"""

import time
import pytest
from engram.miner.rate_limiter import RateLimiter


@pytest.fixture
def rl() -> RateLimiter:
    return RateLimiter(max_requests=3, window_secs=10)


# ── Basic allow/deny ──────────────────────────────────────────────────────────

def test_first_request_allowed(rl: RateLimiter) -> None:
    assert rl.is_allowed("hotkey_abc") is True


def test_requests_within_limit_allowed(rl: RateLimiter) -> None:
    for _ in range(3):
        assert rl.is_allowed("hotkey_abc") is True


def test_request_over_limit_denied(rl: RateLimiter) -> None:
    for _ in range(3):
        rl.is_allowed("hotkey_abc")
    assert rl.is_allowed("hotkey_abc") is False


def test_different_keys_are_independent(rl: RateLimiter) -> None:
    for _ in range(3):
        rl.is_allowed("key_a")
    assert rl.is_allowed("key_b") is True


def test_check_raises_when_limited(rl: RateLimiter) -> None:
    for _ in range(3):
        rl.check("key_x")
    with pytest.raises(ValueError, match="Slow down"):
        rl.check("key_x")


def test_check_passes_when_within_limit(rl: RateLimiter) -> None:
    rl.check("key_y")  # should not raise


# ── Window expiry ─────────────────────────────────────────────────────────────

def test_window_expires_allows_new_requests() -> None:
    rl = RateLimiter(max_requests=2, window_secs=1)
    rl.is_allowed("k")
    rl.is_allowed("k")
    assert rl.is_allowed("k") is False
    time.sleep(1.05)
    assert rl.is_allowed("k") is True


# ── Stats ────────────────────────────────────────────────────────────────────

def test_stats_reflect_usage(rl: RateLimiter) -> None:
    rl.is_allowed("key_s")
    rl.is_allowed("key_s")
    stats = rl.stats("key_s")
    assert stats["requests_in_window"] == 2
    assert stats["max_requests"] == 3
    assert stats["remaining"] == 1
    assert stats["key"] == "key_s"


def test_stats_empty_key() -> None:
    rl = RateLimiter(max_requests=5, window_secs=60)
    stats = rl.stats("never_used")
    assert stats["requests_in_window"] == 0
    assert stats["remaining"] == 5


# ── Reset ────────────────────────────────────────────────────────────────────

def test_reset_clears_limit(rl: RateLimiter) -> None:
    for _ in range(3):
        rl.is_allowed("key_r")
    assert rl.is_allowed("key_r") is False
    rl.reset("key_r")
    assert rl.is_allowed("key_r") is True


def test_reset_unknown_key_noop(rl: RateLimiter) -> None:
    rl.reset("does_not_exist")  # should not raise
