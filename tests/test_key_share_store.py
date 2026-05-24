"""Tests for engram/miner/key_share_store.py — KeyShareStore."""

import pytest
from pathlib import Path
from engram.miner.key_share_store import KeyShareStore


@pytest.fixture
def store(tmp_path: Path) -> KeyShareStore:
    return KeyShareStore(db_path=tmp_path / "key_shares.db")


# ── Store and retrieve ────────────────────────────────────────────────────────

def test_store_and_get(store: KeyShareStore) -> None:
    store.store("ns_alpha", share_index=1, share_hex="deadbeef", threshold=2, total=3)
    result = store.get("ns_alpha")
    assert result is not None
    assert result["share_index"] == 1
    assert result["share_hex"] == "deadbeef"
    assert result["threshold"] == 2
    assert result["total"] == 3


def test_get_missing_namespace_returns_none(store: KeyShareStore) -> None:
    assert store.get("nonexistent") is None


def test_upsert_overwrites_existing(store: KeyShareStore) -> None:
    store.store("ns_beta", share_index=1, share_hex="aabbcc", threshold=2, total=3)
    store.store("ns_beta", share_index=2, share_hex="ddeeff", threshold=3, total=5)
    result = store.get("ns_beta")
    assert result["share_index"] == 2
    assert result["share_hex"] == "ddeeff"
    assert result["threshold"] == 3


def test_multiple_namespaces_independent(store: KeyShareStore) -> None:
    store.store("ns_one", share_index=1, share_hex="aaaa", threshold=2, total=3)
    store.store("ns_two", share_index=2, share_hex="bbbb", threshold=2, total=3)
    assert store.get("ns_one")["share_hex"] == "aaaa"
    assert store.get("ns_two")["share_hex"] == "bbbb"


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_existing(store: KeyShareStore) -> None:
    store.store("ns_del", share_index=1, share_hex="1234", threshold=2, total=3)
    assert store.delete("ns_del") is True
    assert store.get("ns_del") is None


def test_delete_nonexistent_returns_false(store: KeyShareStore) -> None:
    assert store.delete("never_existed") is False


# ── Persistence ───────────────────────────────────────────────────────────────

def test_persists_across_instances(tmp_path: Path) -> None:
    db = tmp_path / "shares.db"
    s1 = KeyShareStore(db_path=db)
    s1.store("ns_p", share_index=3, share_hex="cafebabe", threshold=2, total=5)
    s2 = KeyShareStore(db_path=db)
    result = s2.get("ns_p")
    assert result is not None
    assert result["share_hex"] == "cafebabe"
    assert result["share_index"] == 3
