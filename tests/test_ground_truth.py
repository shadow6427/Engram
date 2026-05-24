"""Tests for engram/validator/ground_truth.py — GroundTruthManager."""

import json
import numpy as np
import pytest
from pathlib import Path
from engram.validator.ground_truth import GroundTruthEntry, GroundTruthManager


def _make_entry(text: str = "hello", cid: str = "v1::" + "a" * 64) -> GroundTruthEntry:
    return GroundTruthEntry(
        text=text,
        embedding=np.random.rand(4).astype(np.float32),
        cid=cid,
        top_k_cids=[cid],
    )


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries))


# ── Load ──────────────────────────────────────────────────────────────────────

def test_load_valid_entries(tmp_path: Path) -> None:
    path = tmp_path / "gt.jsonl"
    _write_jsonl(path, [
        {"text": "hello", "embedding": [0.1, 0.2, 0.3], "cid": "v1::" + "a" * 64, "top_k_cids": ["v1::" + "a" * 64]},
        {"text": "world", "embedding": [0.4, 0.5, 0.6], "cid": "v1::" + "b" * 64, "top_k_cids": []},
    ])
    mgr = GroundTruthManager(path=str(path))
    assert len(mgr) == 2


def test_load_skips_missing_text(tmp_path: Path) -> None:
    path = tmp_path / "gt.jsonl"
    _write_jsonl(path, [
        {"embedding": [0.1, 0.2], "cid": "v1::" + "a" * 64},
    ])
    mgr = GroundTruthManager(path=str(path))
    assert len(mgr) == 0


def test_load_skips_missing_embedding(tmp_path: Path) -> None:
    path = tmp_path / "gt.jsonl"
    _write_jsonl(path, [
        {"text": "hi", "cid": "v1::" + "a" * 64},
    ])
    mgr = GroundTruthManager(path=str(path))
    assert len(mgr) == 0


def test_load_skips_empty_embedding(tmp_path: Path) -> None:
    path = tmp_path / "gt.jsonl"
    _write_jsonl(path, [
        {"text": "hi", "embedding": [], "cid": "v1::" + "a" * 64},
    ])
    mgr = GroundTruthManager(path=str(path))
    assert len(mgr) == 0


def test_load_skips_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "gt.jsonl"
    path.write_text('{"text": "ok", "embedding": [1.0], "cid": "v1::' + "a" * 64 + '"}\nnot json\n')
    mgr = GroundTruthManager(path=str(path))
    assert len(mgr) == 1


def test_load_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "gt.jsonl"
    path.write_text('\n\n{"text": "ok", "embedding": [1.0], "cid": "v1::' + "a" * 64 + '"}\n\n')
    mgr = GroundTruthManager(path=str(path))
    assert len(mgr) == 1


def test_nonexistent_path_returns_empty() -> None:
    mgr = GroundTruthManager(path="/nonexistent/path/gt.jsonl")
    assert len(mgr) == 0


# ── Add / all_cids ────────────────────────────────────────────────────────────

def test_add_and_count() -> None:
    mgr = GroundTruthManager()
    mgr.add(_make_entry(cid="v1::" + "a" * 64))
    mgr.add(_make_entry(cid="v1::" + "b" * 64))
    assert len(mgr) == 2


def test_all_cids() -> None:
    mgr = GroundTruthManager()
    cid_a = "v1::" + "a" * 64
    cid_b = "v1::" + "b" * 64
    mgr.add(_make_entry(cid=cid_a))
    mgr.add(_make_entry(cid=cid_b))
    assert set(mgr.all_cids()) == {cid_a, cid_b}


# ── Sample ────────────────────────────────────────────────────────────────────

def test_sample_returns_correct_count() -> None:
    mgr = GroundTruthManager()
    for i in range(10):
        mgr.add(_make_entry(cid="v1::" + chr(ord("a") + i) * 64))
    sample = mgr.sample(n=5)
    assert len(sample) == 5


def test_sample_clamps_to_available() -> None:
    mgr = GroundTruthManager()
    mgr.add(_make_entry())
    sample = mgr.sample(n=100)
    assert len(sample) == 1


def test_sample_empty_manager_returns_empty() -> None:
    mgr = GroundTruthManager()
    assert mgr.sample(n=5) == []


def test_sample_returns_valid_entries() -> None:
    mgr = GroundTruthManager()
    mgr.add(_make_entry(text="alpha"))
    result = mgr.sample(n=1)
    assert result[0].text == "alpha"


# ── Save / reload ─────────────────────────────────────────────────────────────

def test_save_and_reload(tmp_path: Path) -> None:
    path = str(tmp_path / "gt.jsonl")
    mgr = GroundTruthManager()
    mgr.add(GroundTruthEntry(
        text="test text",
        embedding=np.array([0.1, 0.2, 0.3], dtype=np.float32),
        cid="v1::" + "c" * 64,
        top_k_cids=["v1::" + "c" * 64],
    ))
    mgr.save(path)

    mgr2 = GroundTruthManager(path=path)
    assert len(mgr2) == 1
    assert mgr2._entries[0].text == "test text"
    assert mgr2._entries[0].cid == "v1::" + "c" * 64
    np.testing.assert_allclose(mgr2._entries[0].embedding, [0.1, 0.2, 0.3], atol=1e-6)
