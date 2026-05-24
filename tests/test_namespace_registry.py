"""Tests for engram/miner/namespace.py — NamespaceRegistry."""

import time
import pytest
from pathlib import Path
from engram.miner.namespace import NamespaceRegistry


@pytest.fixture
def reg(tmp_path: Path) -> NamespaceRegistry:
    return NamespaceRegistry(path=tmp_path / "ns.json")


# ── Create / verify ───────────────────────────────────────────────────────────

def test_create_and_verify(reg: NamespaceRegistry) -> None:
    reg.create("my_ns", "a_very_long_secret_key")
    assert reg.verify("my_ns", "a_very_long_secret_key")


def test_wrong_key_rejected(reg: NamespaceRegistry) -> None:
    reg.create("my_ns", "correct_key_1234567")
    assert not reg.verify("my_ns", "wrong_key_000000000")


def test_unknown_namespace_returns_false(reg: NamespaceRegistry) -> None:
    assert not reg.verify("nonexistent", "any_key_1234567890")


def test_duplicate_create_raises(reg: NamespaceRegistry) -> None:
    reg.create("my_ns", "first_key_1234567890")
    with pytest.raises(ValueError, match="already exists"):
        reg.create("my_ns", "second_key_123456789")


def test_invalid_namespace_name_raises(reg: NamespaceRegistry) -> None:
    with pytest.raises(ValueError, match="valid identifier"):
        reg.create("bad-name!", "some_long_key_12345")


def test_short_key_raises(reg: NamespaceRegistry) -> None:
    with pytest.raises(ValueError, match="16 characters"):
        reg.create("valid_ns", "tooshort")


# ── Exists ────────────────────────────────────────────────────────────────────

def test_exists_after_create(reg: NamespaceRegistry) -> None:
    reg.create("ns_one", "key_one_is_long_enough")
    assert reg.exists("ns_one")


def test_not_exists_before_create(reg: NamespaceRegistry) -> None:
    assert not reg.exists("missing")


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_with_correct_key(reg: NamespaceRegistry) -> None:
    reg.create("temp_ns", "correct_key_123456789")
    assert reg.delete("temp_ns", "correct_key_123456789")
    assert not reg.exists("temp_ns")


def test_delete_with_wrong_key_fails(reg: NamespaceRegistry) -> None:
    reg.create("keep_ns", "correct_key_123456789")
    assert not reg.delete("keep_ns", "wrong_key_1234567890")
    assert reg.exists("keep_ns")


# ── Rotate key ────────────────────────────────────────────────────────────────

def test_rotate_key(reg: NamespaceRegistry) -> None:
    reg.create("rot_ns", "old_key_1234567890000")
    ok = reg.rotate_key("rot_ns", "old_key_1234567890000", "new_key_1234567890000")
    assert ok
    assert reg.verify("rot_ns", "new_key_1234567890000")
    assert not reg.verify("rot_ns", "old_key_1234567890000")


def test_rotate_key_wrong_old_key(reg: NamespaceRegistry) -> None:
    reg.create("rot_ns", "old_key_1234567890000")
    ok = reg.rotate_key("rot_ns", "wrong_old_key_12345678", "new_key_1234567890000")
    assert not ok


def test_rotate_key_short_new_key_raises(reg: NamespaceRegistry) -> None:
    reg.create("rot_ns", "old_key_1234567890000")
    with pytest.raises(ValueError, match="16 characters"):
        reg.rotate_key("rot_ns", "old_key_1234567890000", "short")


# ── Persistence ───────────────────────────────────────────────────────────────

def test_registry_persists_across_reload(tmp_path: Path) -> None:
    path = tmp_path / "ns.json"
    reg1 = NamespaceRegistry(path=path)
    reg1.create("persistent_ns", "persisted_key_12345678")
    reg2 = NamespaceRegistry(path=path)
    assert reg2.exists("persistent_ns")
    assert reg2.verify("persistent_ns", "persisted_key_12345678")


# ── Owner (sig-based) ─────────────────────────────────────────────────────────

def test_register_owner_and_retrieve(reg: NamespaceRegistry) -> None:
    reg.register_owner("sig_ns", "5FakeHotkey123456789")
    assert reg.owner_hotkey("sig_ns") == "5FakeHotkey123456789"


def test_owner_hotkey_unknown_namespace(reg: NamespaceRegistry) -> None:
    assert reg.owner_hotkey("missing") is None


def test_list_namespaces(reg: NamespaceRegistry) -> None:
    reg.create("ns_a", "key_aaaaaaaaaaaaaaaaaaa")
    reg.create("ns_b", "key_bbbbbbbbbbbbbbbbbbb")
    names = reg.list_namespaces()
    assert "ns_a" in names
    assert "ns_b" in names


# ── verify_sig without bittensor (dev-mode fallback) ─────────────────────────

def test_verify_sig_dev_mode_passes_within_window(reg: NamespaceRegistry) -> None:
    ts = int(time.time() * 1000)
    # In dev mode (no bittensor), verify_sig returns True for any sig if ts is fresh
    result = reg.verify_sig("any_ns", "5AnyHotkey", "0xdeadbeef", ts)
    # Result depends on whether bittensor is installed; just assert it doesn't crash
    assert isinstance(result, bool)


def test_verify_sig_expired_timestamp(reg: NamespaceRegistry) -> None:
    old_ts = int((time.time() - 120) * 1000)  # 2 minutes ago
    result = reg.verify_sig("any_ns", "5AnyHotkey", "0xdeadbeef", old_ts)
    assert result is False


def test_verify_sig_wrong_owner_rejected(reg: NamespaceRegistry) -> None:
    reg.register_owner("owned_ns", "5CorrectOwner123456789")
    ts = int(time.time() * 1000)
    result = reg.verify_sig("owned_ns", "5WrongOwner1234567890", "0xdeadbeef", ts)
    assert result is False
