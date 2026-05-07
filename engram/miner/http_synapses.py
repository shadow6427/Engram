"""Helpers for converting miner HTTP JSON bodies into protocol synapses."""

from __future__ import annotations

from typing import Any

from engram.protocol import IngestSynapse, QuerySynapse


def ingest_synapse_from_body(body: dict[str, Any]) -> IngestSynapse:
    """Build an IngestSynapse from a JSON request body."""
    return IngestSynapse(
        text=body.get("text"),
        raw_embedding=body.get("raw_embedding"),
        metadata=body.get("metadata") or {},
        model_version=body.get("model_version") or "v1",
        namespace=body.get("namespace") or None,
        namespace_hotkey=body.get("namespace_hotkey") or None,
        namespace_sig=body.get("namespace_sig") or None,
        namespace_timestamp_ms=body.get("namespace_timestamp_ms") or None,
        namespace_key=body.get("namespace_key") or None,
    )


def query_synapse_from_body(body: dict[str, Any]) -> QuerySynapse:
    """Build a QuerySynapse from a JSON request body."""
    return QuerySynapse(
        query_text=body.get("query_text"),
        query_vector=body.get("query_vector"),
        top_k=int(body.get("top_k", 10)),
        namespace=body.get("namespace") or None,
        namespace_hotkey=body.get("namespace_hotkey") or None,
        namespace_sig=body.get("namespace_sig") or None,
        namespace_timestamp_ms=body.get("namespace_timestamp_ms") or None,
        namespace_key=body.get("namespace_key") or None,
    )
