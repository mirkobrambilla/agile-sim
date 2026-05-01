"""Asset generation dry-run and mock client."""

from __future__ import annotations

from pathlib import Path

import yaml

from harness.assets import run_jobs, plan_jobs, load_manifest, filter_jobs


def test_dry_run_no_client(tmp_path: Path) -> None:
    mp = tmp_path / "manifest.yaml"
    mp.write_text(
        yaml.safe_dump(
            {
                "defaults": {"out_root": "sprites"},
                "sets": [{"id": "t", "items": [{"id": "u", "prompt": "hello"}]}],
            }
        ),
        encoding="utf-8",
    )
    m = load_manifest(mp)
    jobs = plan_jobs(m, root=tmp_path)
    rep = run_jobs(jobs, client=None, dry_run=True)
    assert rep.would_generate == 1
    assert rep.generated == 0
    assert rep.failed == 0


class _FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def chat_image_to_file(self, model: str, prompt: str, output_path: Path, **kwargs: object) -> bool:
        self.calls += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        return True


def test_skip_when_hash_matches(tmp_path: Path) -> None:
    mp = tmp_path / "manifest.yaml"
    mp.write_text(
        yaml.safe_dump(
            {
                "defaults": {"out_root": "sprites"},
                "sets": [{"id": "t", "items": [{"id": "u", "prompt": "same"}]}],
            }
        ),
        encoding="utf-8",
    )
    m = load_manifest(mp)
    jobs = plan_jobs(m, root=tmp_path)
    fc = _FakeClient()
    r1 = run_jobs(jobs, fc, force=False)
    assert fc.calls == 1
    assert r1.generated == 1
    r2 = run_jobs(jobs, fc, force=False)
    assert fc.calls == 1
    assert r2.skipped == 1
    assert r2.generated == 0


def test_force_regenerates(tmp_path: Path) -> None:
    mp = tmp_path / "manifest.yaml"
    mp.write_text(
        yaml.safe_dump(
            {
                "defaults": {"out_root": "sprites"},
                "sets": [{"id": "t", "items": [{"id": "u", "prompt": "same"}]}],
            }
        ),
        encoding="utf-8",
    )
    jobs = plan_jobs(load_manifest(mp), root=tmp_path)
    fc = _FakeClient()
    run_jobs(jobs, fc, force=False)
    run_jobs(jobs, fc, force=True)
    assert fc.calls == 2

