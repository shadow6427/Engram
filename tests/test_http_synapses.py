"""Regression tests for miner HTTP request body to synapse conversion."""

from __future__ import annotations

from engram.miner.http_synapses import ingest_synapse_from_body, query_synapse_from_body


def test_ingest_synapse_from_body_preserves_signed_namespace_fields() -> None:
    body = {
        "text": "private memory",
        "metadata": {"source": "test"},
        "model_version": "v2",
        "namespace": "team_alpha",
        "namespace_hotkey": "5FakeOwner",
        "namespace_sig": "0xabc123",
        "namespace_timestamp_ms": 1778112345000,
    }

    synapse = ingest_synapse_from_body(body)

    assert synapse.text == "private memory"
    assert synapse.metadata == {"source": "test"}
    assert synapse.model_version == "v2"
    assert synapse.namespace == "team_alpha"
    assert synapse.namespace_hotkey == "5FakeOwner"
    assert synapse.namespace_sig == "0xabc123"
    assert synapse.namespace_timestamp_ms == 1778112345000
    assert synapse.namespace_key is None


def test_query_synapse_from_body_preserves_signed_namespace_fields() -> None:
    body = {
        "query_text": "private search",
        "top_k": "7",
        "namespace": "team_alpha",
        "namespace_hotkey": "5FakeOwner",
        "namespace_sig": "0xdef456",
        "namespace_timestamp_ms": 1778112345001,
    }

    synapse = query_synapse_from_body(body)

    assert synapse.query_text == "private search"
    assert synapse.top_k == 7
    assert synapse.namespace == "team_alpha"
    assert synapse.namespace_hotkey == "5FakeOwner"
    assert synapse.namespace_sig == "0xdef456"
    assert synapse.namespace_timestamp_ms == 1778112345001
    assert synapse.namespace_key is None


def test_synapse_from_body_still_supports_legacy_namespace_key() -> None:
    ingest = ingest_synapse_from_body({
        "text": "legacy private memory",
        "namespace": "legacy_ns",
        "namespace_key": "legacy-secret",
    })
    query = query_synapse_from_body({
        "query_vector": [0.1, 0.2, 0.3],
        "namespace": "legacy_ns",
        "namespace_key": "legacy-secret",
    })

    assert ingest.namespace == "legacy_ns"
    assert ingest.namespace_key == "legacy-secret"
    assert ingest.namespace_sig is None
    assert query.namespace == "legacy_ns"
    assert query.namespace_key == "legacy-secret"
    assert query.namespace_sig is None
