"""Tests for engram/miner/ingest.py — IngestHandler."""

from __future__ import annotations
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from engram.miner.ingest import IngestHandler, _add_dp_noise
from engram.miner.store import FAISSStore, VectorRecord
from engram.miner.namespace import NamespaceRegistry
from engram.protocol import IngestSynapse
from pathlib import Path


DIM = 4


def make_embedder(dim: int = DIM):
    emb = MagicMock()
    emb.embed.return_value = np.ones(dim, dtype=np.float32)
    return emb


def make_store() -> FAISSStore:
    return FAISSStore(dim=DIM)


def make_handler(
    dim: int = DIM,
    namespace_registry=None,
    dp_epsilon: float | None = None,
) -> IngestHandler:
    return IngestHandler(
        store=FAISSStore(dim=dim),
        embedder=make_embedder(dim),
        namespace_registry=namespace_registry,
        dp_epsilon=dp_epsilon,
    )


# ── Basic ingest ──────────────────────────────────────────────────────────────

def test_ingest_text_returns_cid() -> None:
    handler = make_handler()
    syn = IngestSynapse(text="hello world")
    result = handler.handle(syn)
    assert result.cid is not None
    assert result.error is None


def test_ingest_raw_embedding_returns_cid() -> None:
    from engram.config import EMBEDDING_DIM
    handler = make_handler(dim=EMBEDDING_DIM)
    syn = IngestSynapse(raw_embedding=[0.1] * EMBEDDING_DIM)
    result = handler.handle(syn)
    assert result.cid is not None
    assert result.error is None


def test_ingest_stores_vector_in_store() -> None:
    store = make_store()
    handler = IngestHandler(store=store, embedder=make_embedder(), dp_epsilon=None)
    syn = IngestSynapse(text="store me")
    result = handler.handle(syn)
    assert store.count() == 1
    assert store.get(result.cid) is not None


# ── Validation errors ─────────────────────────────────────────────────────────

def test_missing_text_and_embedding_returns_error() -> None:
    handler = make_handler()
    syn = IngestSynapse()
    result = handler.handle(syn)
    assert result.error is not None
    assert result.cid is None


def test_text_too_long_returns_error() -> None:
    handler = make_handler()
    syn = IngestSynapse(text="x" * 100_001)
    result = handler.handle(syn)
    assert result.error is not None


def test_wrong_embedding_dim_returns_error() -> None:
    handler = make_handler(dim=DIM)
    syn = IngestSynapse(raw_embedding=[0.1] * (DIM + 1))
    result = handler.handle(syn)
    assert result.error is not None


def test_metadata_too_large_returns_error() -> None:
    handler = make_handler()
    syn = IngestSynapse(text="ok", metadata={"big": "x" * 100_000})
    result = handler.handle(syn)
    assert result.error is not None


# ── Namespace auth ────────────────────────────────────────────────────────────

def test_public_namespace_no_auth_required() -> None:
    handler = make_handler()
    syn = IngestSynapse(text="public data")
    result = handler.handle(syn)
    assert result.error is None


def test_namespace_without_registry_returns_error() -> None:
    handler = make_handler(namespace_registry=None)
    syn = IngestSynapse(text="private", namespace="my_ns", namespace_key="longkey1234567890")
    result = handler.handle(syn)
    assert result.error is not None


def test_namespace_legacy_key_creates_and_stores(tmp_path: Path) -> None:
    reg = NamespaceRegistry(path=tmp_path / "ns.json")
    handler = IngestHandler(
        store=make_store(),
        embedder=make_embedder(),
        namespace_registry=reg,
        dp_epsilon=None,
    )
    syn = IngestSynapse(text="private data", namespace="my_ns", namespace_key="longkey1234567890")
    result = handler.handle(syn)
    assert result.error is None
    assert result.cid is not None
    assert reg.exists("my_ns")


def test_namespace_wrong_legacy_key_rejected(tmp_path: Path) -> None:
    reg = NamespaceRegistry(path=tmp_path / "ns.json")
    reg.create("my_ns", "correct_key_12345678901")
    handler = IngestHandler(
        store=make_store(),
        embedder=make_embedder(),
        namespace_registry=reg,
        dp_epsilon=None,
    )
    syn = IngestSynapse(text="private", namespace="my_ns", namespace_key="wrong_key_12345678")
    result = handler.handle(syn)
    assert result.error is not None


# ── DP noise ──────────────────────────────────────────────────────────────────

def test_dp_noise_changes_embedding() -> None:
    emb = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    noisy = _add_dp_noise(emb, epsilon=1.0)
    assert not np.allclose(emb, noisy)


def test_dp_noise_preserves_unit_norm() -> None:
    emb = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    noisy = _add_dp_noise(emb, epsilon=1.0)
    assert abs(np.linalg.norm(noisy) - 1.0) < 0.01


def test_dp_noise_applied_for_private_namespace(tmp_path: Path) -> None:
    reg = NamespaceRegistry(path=tmp_path / "ns.json")
    store = make_store()
    handler = IngestHandler(
        store=store,
        embedder=make_embedder(),
        namespace_registry=reg,
        dp_epsilon=1.0,
    )
    syn = IngestSynapse(text="private", namespace="priv_ns", namespace_key="longkey12345678901")
    result = handler.handle(syn)
    assert result.error is None


def test_dp_noise_disabled_for_public_namespace(tmp_path: Path) -> None:
    store = make_store()
    embedder = make_embedder()
    handler = IngestHandler(store=store, embedder=embedder, dp_epsilon=1.0)
    syn = IngestSynapse(text="public")
    result = handler.handle(syn)
    assert result.error is None
    # Embedding stored should match what embedder returned (no noise on public)
    record = store.get(result.cid)
    assert record is not None
    np.testing.assert_allclose(record.embedding, np.ones(DIM, dtype=np.float32), atol=1e-5)
