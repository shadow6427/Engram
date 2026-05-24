"""Tests for engram/protocol.py — synapse definitions."""

import pytest
from engram.protocol import (
    IngestSynapse,
    QuerySynapse,
    ChallengeSynapse,
    KeyShareSynapse,
    KeyShareRetrieve,
)


# ── IngestSynapse ─────────────────────────────────────────────────────────────

def test_ingest_synapse_defaults() -> None:
    syn = IngestSynapse()
    assert syn.text is None
    assert syn.raw_embedding is None
    assert syn.metadata == {}
    assert syn.cid is None
    assert syn.error is None
    assert syn.namespace is None


def test_ingest_synapse_with_text() -> None:
    syn = IngestSynapse(text="hello world")
    assert syn.text == "hello world"
    assert syn.deserialize() is None  # cid not set yet


def test_ingest_synapse_with_embedding() -> None:
    syn = IngestSynapse(raw_embedding=[0.1, 0.2, 0.3])
    assert len(syn.raw_embedding) == 3


def test_ingest_synapse_cid_deserialize() -> None:
    syn = IngestSynapse(text="x", cid="v1::" + "a" * 64)
    assert syn.deserialize() == "v1::" + "a" * 64


def test_ingest_synapse_namespace_fields() -> None:
    syn = IngestSynapse(
        text="private",
        namespace="my_ns",
        namespace_hotkey="5ABC",
        namespace_sig="0xDEAD",
        namespace_timestamp_ms=1234567890,
    )
    assert syn.namespace == "my_ns"
    assert syn.namespace_hotkey == "5ABC"
    assert syn.namespace_sig == "0xDEAD"
    assert syn.namespace_timestamp_ms == 1234567890


# ── QuerySynapse ──────────────────────────────────────────────────────────────

def test_query_synapse_defaults() -> None:
    syn = QuerySynapse()
    assert syn.query_text is None
    assert syn.query_vector is None
    assert syn.top_k == 10
    assert syn.results == []
    assert syn.error is None


def test_query_synapse_top_k_bounds() -> None:
    syn = QuerySynapse(top_k=1)
    assert syn.top_k == 1
    syn2 = QuerySynapse(top_k=100)
    assert syn2.top_k == 100


def test_query_synapse_top_k_too_low_raises() -> None:
    with pytest.raises(Exception):
        QuerySynapse(top_k=0)


def test_query_synapse_top_k_too_high_raises() -> None:
    with pytest.raises(Exception):
        QuerySynapse(top_k=101)


def test_query_synapse_deserialize() -> None:
    syn = QuerySynapse(results=[{"cid": "v1::abc", "score": 0.9}])
    assert syn.deserialize() == [{"cid": "v1::abc", "score": 0.9}]


# ── ChallengeSynapse ──────────────────────────────────────────────────────────

def test_challenge_synapse_required_fields() -> None:
    syn = ChallengeSynapse(
        cid="v1::" + "a" * 64,
        nonce_hex="deadbeef" * 8,
        expires_at=9999999999,
    )
    assert syn.cid == "v1::" + "a" * 64
    assert syn.embedding_hash is None
    assert syn.proof is None


def test_challenge_synapse_deserialize() -> None:
    syn = ChallengeSynapse(
        cid="v1::" + "a" * 64,
        nonce_hex="abc",
        expires_at=0,
        embedding_hash="hash123",
        proof="proof456",
    )
    result = syn.deserialize()
    assert result["embedding_hash"] == "hash123"
    assert result["proof"] == "proof456"


# ── KeyShareSynapse ───────────────────────────────────────────────────────────

def test_key_share_synapse_fields() -> None:
    syn = KeyShareSynapse(
        namespace="my_ns",
        share_index=1,
        share_hex="deadbeef",
        threshold=2,
        total=3,
    )
    assert syn.namespace == "my_ns"
    assert syn.share_index == 1
    assert syn.share_hex == "deadbeef"
    assert syn.threshold == 2
    assert syn.total == 3
    assert syn.stored is False
    assert syn.error is None


def test_key_share_synapse_deserialize() -> None:
    syn = KeyShareSynapse(
        namespace="ns", share_index=1, share_hex="ff",
        threshold=2, total=3, stored=True,
    )
    assert syn.deserialize() is True


# ── KeyShareRetrieve ──────────────────────────────────────────────────────────

def test_key_share_retrieve_fields() -> None:
    syn = KeyShareRetrieve(namespace="my_ns")
    assert syn.namespace == "my_ns"
    assert syn.share_index is None
    assert syn.share_hex is None
    assert syn.threshold is None
    assert syn.total is None
    assert syn.error is None


def test_key_share_retrieve_deserialize() -> None:
    syn = KeyShareRetrieve(
        namespace="ns",
        share_index=2,
        share_hex="cafebabe",
        threshold=2,
        total=3,
    )
    result = syn.deserialize()
    assert result["share_index"] == 2
    assert result["share_hex"] == "cafebabe"
