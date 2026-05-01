"""Manifest-driven image generation via OpenRouter (repeatable, cache-friendly)."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml
from pydantic import BaseModel, Field


class DefaultsModel(BaseModel):
    model: str = "google/gemini-3.1-flash-image-preview"
    aspect_ratio: str = "1:1"
    out_root: str = "harness/web/static/sprites"


class ItemModel(BaseModel):
    id: str
    prompt: str


class SetModel(BaseModel):
    id: str
    model: str | None = None
    aspect_ratio: str | None = None
    out_root: str | None = None
    style: str | None = None
    items: list[ItemModel] = Field(default_factory=list)


class ManifestModel(BaseModel):
    defaults: DefaultsModel = Field(default_factory=DefaultsModel)
    sets: list[SetModel] = Field(default_factory=list)


@dataclass
class AssetJob:
    set_id: str
    item_id: str
    prompt: str
    model: str
    aspect_ratio: str
    output_png: Path
    hash_path: Path


@dataclass
class AssetReport:
    planned: int = 0
    skipped: int = 0
    generated: int = 0
    failed: int = 0
    would_generate: int = 0
    errors: list[str] = field(default_factory=list)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_manifest(path: Path | None = None) -> ManifestModel:
    p = path or repo_root() / "assets" / "manifest.yaml"
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return ManifestModel.model_validate(data)


def _interpolate(prompt: str, style: str | None) -> str:
    s = style or ""
    return prompt.replace("{style}", s).replace("{style;}", s)


def job_output_image_path(job: AssetJob) -> Path | None:
    """Resolved image path on disk (``.png`` or ``.jpg`` / ``.webp`` from API)."""

    stem = job.output_png.with_suffix("")
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        p = stem.with_suffix(ext)
        if p.is_file():
            return p
    return None


def plan_jobs(manifest: ManifestModel, *, root: Path | None = None) -> list[AssetJob]:
    root = root or repo_root()
    d = manifest.defaults
    jobs: list[AssetJob] = []
    for st in manifest.sets:
        model = st.model or d.model
        ar = st.aspect_ratio or d.aspect_ratio
        out_rel = Path(st.out_root or d.out_root)
        out_base = root / out_rel
        for it in st.items:
            pn = _interpolate(it.prompt, st.style)
            png = out_base / st.id / f"{it.id}.png"
            hsh = out_base / st.id / f"{it.id}.sha256"
            jobs.append(
                AssetJob(
                    set_id=st.id,
                    item_id=it.id,
                    prompt=pn.strip(),
                    model=model,
                    aspect_ratio=ar,
                    output_png=png.resolve(),
                    hash_path=hsh.resolve(),
                )
            )
    return jobs


def job_cache_key(job: AssetJob) -> str:
    payload = f"{job.model}\n{job.aspect_ratio}\n{job.prompt}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _append_log(log_path: Path, row: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def run_jobs(
    jobs: list[AssetJob],
    client: Any,
    *,
    force: bool = False,
    dry_run: bool = False,
    log_file: Path | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> AssetReport:
    rep = AssetReport(planned=len(jobs))
    log_path = log_file or (repo_root() / "assets" / ".log" / "asset_calls.jsonl")

    def prog(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    for job in jobs:
        key = job_cache_key(job)
        existing = job_output_image_path(job)
        if (
            not force
            and existing is not None
            and job.hash_path.is_file()
            and job.hash_path.read_text(encoding="utf-8").strip() == key
        ):
            rep.skipped += 1
            prog(f"skip {job.set_id}/{job.item_id}")
            continue

        if dry_run:
            prog(f"dry-run {job.set_id}/{job.item_id} model={job.model} ar={job.aspect_ratio}")
            prog(f"  prompt: {job.prompt[:120]}{'…' if len(job.prompt) > 120 else ''}")
            rep.would_generate += 1
            continue

        t0 = time.perf_counter()
        ok = client.chat_image_to_file(
            job.model,
            job.prompt,
            job.output_png,
            aspect_ratio=job.aspect_ratio,
        )
        elapsed = round(time.perf_counter() - t0, 3)
        written = job_output_image_path(job)
        size_b = written.stat().st_size if written is not None else 0
        path_log = str(written) if written is not None else str(job.output_png)
        _append_log(
            log_path,
            {
                "ts": time.time(),
                "set": job.set_id,
                "item": job.item_id,
                "model": job.model,
                "aspect_ratio": job.aspect_ratio,
                "path": path_log,
                "ok": ok,
                "bytes": size_b,
                "elapsed_s": elapsed,
            },
        )
        if not ok:
            rep.failed += 1
            rep.errors.append(f"{job.set_id}/{job.item_id}: no image in response")
            prog(f"FAIL {job.set_id}/{job.item_id}")
            continue

        job.hash_path.parent.mkdir(parents=True, exist_ok=True)
        job.hash_path.write_text(key + "\n", encoding="utf-8")
        rep.generated += 1
        prog(f"ok {job.set_id}/{job.item_id} {size_b} bytes {elapsed}s")

    return rep


def filter_jobs(
    jobs: list[AssetJob],
    *,
    set_id: str | None = None,
    item_ref: str | None = None,
) -> list[AssetJob]:
    """item_ref format: ``set_id/item_id`` (e.g. default/happy)."""

    out = jobs
    if item_ref:
        parts = item_ref.split("/", 1)
        if len(parts) != 2:
            raise ValueError("--item must be SET/item_id, e.g. default/happy")
        sid, iid = parts[0].strip(), parts[1].strip()
        out = [j for j in out if j.set_id == sid and j.item_id == iid]
    elif set_id:
        out = [j for j in out if j.set_id == set_id.strip()]
    return out


def list_status(manifest: ManifestModel, *, root: Path | None = None) -> list[dict[str, Any]]:
    root = root or repo_root()
    rows: list[dict[str, Any]] = []
    for job in plan_jobs(manifest, root=root):
        key = job_cache_key(job)
        existing = job_output_image_path(job)
        on_disk = existing is not None
        stale = True
        if on_disk and job.hash_path.is_file():
            stale = job.hash_path.read_text(encoding="utf-8").strip() != key
        rel_display = (
            str(existing.relative_to(root)) if existing is not None else str(job.output_png.relative_to(root))
        )
        rows.append(
            {
                "set": job.set_id,
                "item": job.item_id,
                "path": rel_display,
                "cached": on_disk and not stale,
                "missing": not on_disk,
                "stale": on_disk and stale,
            }
        )
    return rows
