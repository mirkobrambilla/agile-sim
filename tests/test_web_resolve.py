"""Path resolution for web URLs."""

from __future__ import annotations

import json
from pathlib import Path

from harness.web.resolve import ResolvedBatch, resolve_slug_under_runs, resolve_path


def test_manifest_wins_over_summary_at_batch_root(tmp_path: Path) -> None:
    b = tmp_path / "batch1"
    b.mkdir()
    (b / "manifest.json").write_text(json.dumps({"runs": []}), encoding="utf-8")
    (b / "summary.json").write_text(json.dumps({"note": "aggregate"}), encoding="utf-8")
    r = resolve_path(runs_dir=tmp_path, user_path=b)
    assert isinstance(r, ResolvedBatch)


def test_prefix_unique_resolves(tmp_path: Path) -> None:
    b = tmp_path / "batch_abc123uniqueZ"
    b.mkdir()
    (b / "manifest.json").write_text("{}", encoding="utf-8")
    r, amb = resolve_slug_under_runs(runs_dir=tmp_path, slug="batch_abc123")
    assert amb == []
    assert isinstance(r, ResolvedBatch)
    assert r.batch_dir.name == "batch_abc123uniqueZ"


def test_prefix_ambiguous_returns_names(tmp_path: Path) -> None:
    for name in ("batch_pre_a", "batch_pre_b"):
        d = tmp_path / name
        d.mkdir()
        (d / "manifest.json").write_text("{}", encoding="utf-8")
    _r, amb = resolve_slug_under_runs(runs_dir=tmp_path, slug="batch_pre")
    assert len(amb) == 2
