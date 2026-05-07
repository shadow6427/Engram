"""Tests for vector store implementations."""

import sys
import types

import numpy as np
import pytest

from engram.miner.store import FAISSStore, QdrantStore, VectorRecord, _PUBLIC_NS


@pytest.fixture
def store():
    return FAISSStore(dim=4)


def make_record(cid: str, vec: list[float]) -> VectorRecord:
    return VectorRecord(
        cid=cid,
        embedding=np.array(vec, dtype=np.float32),
        metadata={"source": "test"},
    )


def test_upsert_and_count(store):
    store.upsert(make_record("cid1", [1.0, 0.0, 0.0, 0.0]))
    assert store.count() == 1


def test_search_returns_results(store):
    store.upsert(make_record("cid1", [1.0, 0.0, 0.0, 0.0]))
    store.upsert(make_record("cid2", [0.0, 1.0, 0.0, 0.0]))
    results = store.search(np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32), top_k=2)
    assert len(results) > 0
    assert results[0].cid == "cid1"


def test_get_existing(store):
    store.upsert(make_record("cid1", [1.0, 0.0, 0.0, 0.0]))
    record = store.get("cid1")
    assert record is not None
    assert record.cid == "cid1"


def test_get_missing(store):
    assert store.get("nonexistent") is None


def test_delete(store):
    store.upsert(make_record("cid1", [1.0, 0.0, 0.0, 0.0]))
    assert store.delete("cid1")
    assert store.get("cid1") is None


def test_search_empty(store):
    results = store.search(np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32))
    assert results == []


# ── QdrantStore.list regression tests ────────────────────────────────────────

class _FakeMatchValue:
    def __init__(self, value):
        self.value = value


class _FakeFieldCondition:
    def __init__(self, key, match):
        self.key = key
        self.match = match


class _FakeFilter:
    def __init__(self, must):
        self.must = must


class _FakePoint:
    def __init__(self, payload):
        self.payload = payload


class _FakeQdrantClient:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def scroll(self, **kwargs):
        self.calls.append(kwargs)
        if not self.pages:
            return [], None
        page, next_offset = self.pages.pop(0)
        return page, next_offset


@pytest.fixture
def fake_qdrant_models(monkeypatch):
    qdrant = types.ModuleType("qdrant_client")
    models = types.ModuleType("qdrant_client.models")
    models.Filter = _FakeFilter
    models.FieldCondition = _FakeFieldCondition
    models.MatchValue = _FakeMatchValue
    qdrant.models = models
    monkeypatch.setitem(sys.modules, "qdrant_client", qdrant)
    monkeypatch.setitem(sys.modules, "qdrant_client.models", models)


def _qdrant_store(client: _FakeQdrantClient) -> QdrantStore:
    store = QdrantStore.__new__(QdrantStore)
    store._client = client
    store._collection = "engram"
    return store


def _filter_values(call):
    return {condition.key: condition.match.value for condition in call["scroll_filter"].must}


def test_qdrant_list_filters_public_namespace_and_returns_flat_metadata(fake_qdrant_models):
    client = _FakeQdrantClient([
        ([
            _FakePoint({
                "cid": "public_cid",
                "_ns": _PUBLIC_NS,
                "source": "cli",
                "type": "text",
            }),
        ], None),
    ])
    store = _qdrant_store(client)

    records = store.list(namespace=_PUBLIC_NS)

    assert records == [
        {
            "cid": "public_cid",
            "metadata": {"source": "cli", "type": "text"},
        }
    ]
    assert _filter_values(client.calls[0]) == {"_ns": _PUBLIC_NS}


def test_qdrant_list_filters_private_namespace_with_metadata(fake_qdrant_models):
    client = _FakeQdrantClient([
        ([
            _FakePoint({
                "cid": "private_cid",
                "_ns": "team_alpha",
                "source": "sdk",
                "type": "pdf",
            }),
        ], None),
    ])
    store = _qdrant_store(client)

    records = store.list(filter={"type": "pdf"}, namespace="team_alpha")

    assert records == [
        {
            "cid": "private_cid",
            "metadata": {"source": "sdk", "type": "pdf"},
        }
    ]
    assert _filter_values(client.calls[0]) == {"_ns": "team_alpha", "type": "pdf"}


def test_qdrant_list_treats_offset_as_skip_count(fake_qdrant_models):
    client = _FakeQdrantClient([
        ([
            _FakePoint({"cid": "cid_1", "_ns": _PUBLIC_NS}),
            _FakePoint({"cid": "cid_2", "_ns": _PUBLIC_NS}),
        ], "cursor_2"),
        ([
            _FakePoint({"cid": "cid_3", "_ns": _PUBLIC_NS}),
        ], None),
    ])
    store = _qdrant_store(client)

    records = store.list(limit=2, offset=1)

    assert [record["cid"] for record in records] == ["cid_2", "cid_3"]
    assert client.calls[0]["offset"] is None
    assert client.calls[1]["offset"] == "cursor_2"
