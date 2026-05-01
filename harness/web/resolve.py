"""Resolve filesystem paths under runs/ to web paths and metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ResolvedRun:
    """Absolute path to a run directory that has summary.json."""

    run_dir: Path
    """URL path under /runs/, e.g. run_abc or batch_xyz/sub_000."""


@dataclass(frozen=True)
class ResolvedBatch:
    batch_dir: Path


def _has_summary(d: Path) -> bool:
    return d.is_dir() and (d / "summary.json").exists()


def _has_manifest(d: Path) -> bool:
    return d.is_dir() and (d / "manifest.json").exists()


def resolve_path(*, runs_dir: Path, user_path: Path | None) -> ResolvedRun | ResolvedBatch | None:
    """Classify a path inside runs_dir."""

    runs_dir = runs_dir.resolve()
    if user_path is None:
        return None
    p = user_path if user_path.is_absolute() else (runs_dir / user_path)
    p = p.resolve()
    if not str(p).startswith(str(runs_dir)):
        return None
    # Batch roots use manifest.json; prefer that over summary.json when both exist.
    if _has_manifest(p):
        return ResolvedBatch(batch_dir=p)
    if _has_summary(p):
        return ResolvedRun(run_dir=p)
    # child of batch
    if p.parent != runs_dir and _has_manifest(p.parent) and _has_summary(p):
        return ResolvedRun(run_dir=p)
    return None


def resolve_slug_under_runs(
    *, runs_dir: Path, slug: str
) -> tuple[ResolvedRun | ResolvedBatch | None, list[str]]:
    """Resolve a URL path segment like ``batch_…/child`` to a run or batch.

    Returns ``(resolved, ambiguous_names)``. If the slug is an incomplete top-level
    directory prefix and more than one folder matches, ``ambiguous_names`` lists them
    (caller should return a helpful error). For multi-segment paths only exact paths apply.
    """

    runs_dir = runs_dir.resolve()
    slug = slug.strip().strip("/")
    if not slug:
        return None, []

    direct = resolve_path(runs_dir=runs_dir, user_path=runs_dir / slug)
    if direct is not None:
        return direct, []

    if "/" in slug:
        return None, []

    matches = sorted(
        [p for p in runs_dir.iterdir() if p.is_dir() and p.name.startswith(slug)],
        key=lambda x: x.name,
    )
    if len(matches) == 1:
        r = resolve_path(runs_dir=runs_dir, user_path=matches[0])
        return r, []
    if len(matches) > 1:
        return None, [p.name for p in matches]
    return None, []


def run_url_path(*, runs_dir: Path, run_dir: Path) -> str:
    runs_dir = runs_dir.resolve()
    run_dir = run_dir.resolve()
    rel = run_dir.relative_to(runs_dir)
    return str(rel).replace("\\", "/")


def newest_under(runs_dir: Path) -> Path | None:
    runs_dir = runs_dir.resolve()
    if not runs_dir.is_dir():
        return None
    candidates: list[tuple[float, Path]] = []
    for child in runs_dir.iterdir():
        if not child.is_dir():
            continue
        if _has_summary(child):
            mtime = child.stat().st_mtime
            candidates.append((mtime, child))
        elif _has_manifest(child):
            mtime = child.stat().st_mtime
            candidates.append((mtime, child))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def load_manifest_batch(manifest_path: Path) -> dict[str, Any]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))
