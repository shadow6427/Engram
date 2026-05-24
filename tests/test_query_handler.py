"""Tests for engram/miner/query.py — QueryHandler."""

from __future__ import annotations
import numpy as np
import pytest
from unittest.mock import MagicMock
from pathlib import Path

from engram.miner.query import QueryHandler
from engram.miner.store import FAISSStore, VectorRecord
from engram.miner.namespace import NamespaceRegistry
from engram.protocol import QuerySynapse


DIM = 4


def make_embedder():
    emb = MagicMock()
    emb.embed.return_value = np.ones(DIM, dtype=np.float32)
    return emb


def make_store_with_data(namespace: str = "__public__") -> FAISSStore:
    store = FAISSStore(dim=DIM)
    store.upsert(VectorRecord(
        cid="v1::" + "a" * 64,
        embedding=np.ones(DIM, dtype=np.float32),
        metadata={"source": "test"},
        namespace=namespace,
    ))
    return store


def make_handler(store=None, namespace_registry=None) -> QueryHandler:
    return QueryHandler(
        store=store or make_store_with_data(),
        embedder=make_embedder(),
        namespace_registry=namespace_registry,
    )


# ── Basic query ───────────────────────────────────────────────────────────────

def test_query_by_text_returns_results() -> None:
    handler = make_handler()
    syn = QuerySynapse(query_text="hello", top_k=5)
    result = handler.handle(syn)
    assert result.error is None
    assert len(result.results) > 0


def test_query_by_vector_returns_results() -> None:
    handler = make_handler()
    syn = QuerySynapse(query_vector=[1.0] * DIM, top_k=5)
    result = handler.handle(syn)
    assert result.error is None
    assert len(result.results) > 0


def test_query_result_has_expected_fields() -> None:
    handler = make_handler()
    syn = QuerySynapse(query_vector=[1.0] * DIM, top_k=1)
    result = handler.handle(syn)
    r = result.results[0]
    assert "cid" in r
    assert "score" in r
    assert "metadata" in r
    assert "trust_tier" in r


def test_query_top_k_respected() -> None:
    store = FAISSStore(dim=DIM)
    for i in range(5):
        store.upsert(VectorRecord(
            cid="v1::" + chr(ord("a") + i) * 64,
            embedding=np.random.rand(DIM).astype(np.float32),
            metadata={},
        ))
    handler = QueryHandler(store=store, embedder=make_embedder())
    syn = QuerySynapse(query_vector=[1.0] * DIM, top_k=2)
    result = handler.handle(syn)
    assert len(result.results) <= 2


def test_query_latency_ms_populated() -> None:
    handler = make_handler()
    syn = QuerySynapse(query_vector=[1.0] * DIM)
    result = handler.handle(syn)
    assert result.latency_ms is not None
    assert result.latency_ms >= 0


# ── Missing query input ───────────────────────────────────────────────────────

def test_query_no_text_or_vector_returns_error() -> None:
    handler = make_handler()
    syn = QuerySynapse()
    result = handler.handle(syn)
    assert result.error is not None
    assert result.results == []


# ── Namespace auth ────────────────────────────────────────────────────────────

def test_public_query_no_auth_required() -> None:
    handler = make_handler()
    syn = QuerySynapse(query_vector=[1.0] * DIM)
    result = handler.handle(syn)
    assert result.error is None


def test_namespace_query_without_registry_returns_error() -> None:
    handler = QueryHandler(
        store=make_store_with_data(),
        embedder=make_embedder(),
        namespace_registry=None,
    )
    syn = QuerySynapse(query_vector=[1.0] * DIM, namespace="priv_ns", namespace_key="key123")
    result = handler.handle(syn)
    assert result.error is not None


def test_namespace_query_nonexistent_namespace_returns_error(tmp_path: Path) -> None:
    reg = NamespaceRegistry(path=tmp_path / "ns.json")
    handler = QueryHandler(
        store=make_store_with_data(),
        embedder=make_embedder(),
        namespace_registry=reg,
    )
    syn = QuerySynapse(
        query_vector=[1.0] * DIM,
        namespace="ghost_ns",
        namespace_key="longkey1234567890",
    )
    result = handler.handle(syn)
    assert result.error is not None


def test_namespace_query_correct_key_succeeds(tmp_path: Path) -> None:
    reg = NamespaceRegistry(path=tmp_path / "ns.json")
    reg.create("priv_ns", "correct_key_12345678901")
    store = make_store_with_data(namespace="priv_ns")
    handler = QueryHandler(store=store, embedder=make_embedder(), namespace_registry=reg)
    syn = QuerySynapse(
        query_vector=[1.0] * DIM,
        namespace="priv_ns",
        namespace_key="correct_key_12345678901",
        top_k=5,
    )
    result = handler.handle(syn)
    assert result.error is None


def test_namespace_query_wrong_key_returns_error(tmp_path: Path) -> None:
    reg = NamespaceRegistry(path=tmp_path / "ns.json")
    reg.create("priv_ns", "correct_key_12345678901")
    handler = QueryHandler(
        store=make_store_with_data(namespace="priv_ns"),
        embedder=make_embedder(),
        namespace_registry=reg,
    )
    syn = QuerySynapse(
        query_vector=[1.0] * DIM,
        namespace="priv_ns",
        namespace_key="wrong_key_123456789012",
    )
    result = handler.handle(syn)
    assert result.error is not None


# ── Embedder called for text queries ─────────────────────────────────────────

def test_embedder_called_for_text_query() -> None:
    embedder = make_embedder()
    handler = QueryHandler(store=make_store_with_data(), embedder=embedder)
    syn = QuerySynapse(query_text="test query")
    handler.handle(syn)
    embedder.embed.assert_called_once_with("test query")


def test_embedder_not_called_for_vector_query() -> None:
    embedder = make_embedder()
    handler = QueryHandler(store=make_store_with_data(), embedder=embedder)
    syn = QuerySynapse(query_vector=[0.5] * DIM)
    handler.handle(syn)
    embedder.embed.assert_not_called()
