"""Asset manifest planning and cache keys."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from harness.assets import filter_jobs, job_cache_key, load_manifest, plan_jobs


def test_load_and_plan_minimal(tmp_path: Path) -> None:
    mpath = tmp_path / "manifest.yaml"
    mpath.write_text(
        yaml.safe_dump(
            {
                "defaults": {
                    "model": "google/gemini-3.1-flash-image-preview",
                    "aspect_ratio": "1:1",
                    "out_root": "out/sprites",
                },
                "sets": [
                    {
                        "id": "s1",
                        "style": "ST",
                        "items": [{"id": "a", "prompt": "{style} X"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    m = load_manifest(mpath)
    jobs = plan_jobs(m, root=tmp_path)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.set_id == "s1"
    assert j.item_id == "a"
    assert j.prompt == "ST X"
    assert j.output_png == tmp_path / "out" / "sprites" / "s1" / "a.png"


def test_job_cache_key_stable() -> None:
    from harness.assets import AssetJob

    j = AssetJob(
        set_id="s",
        item_id="i",
        prompt="p",
        model="m",
        aspect_ratio="1:1",
        output_png=Path("/tmp/x.png"),
        hash_path=Path("/tmp/x.sha256"),
    )
    assert len(job_cache_key(j)) == 64


def test_filter_item_ref() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        mp = root / "m.yaml"
        mp.write_text(
            yaml.safe_dump(
                {
                    "sets": [
                        {
                            "id": "default",
                            "items": [
                                {"id": "idle", "prompt": "A"},
                                {"id": "happy", "prompt": "B"},
                            ],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        m = load_manifest(mp)
        jobs = plan_jobs(m, root=root)
        f = filter_jobs(jobs, item_ref="default/happy")
        assert len(f) == 1
        assert f[0].item_id == "happy"


def test_filter_bad_item_raises() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        mp = root / "m.yaml"
        mp.write_text(
            yaml.safe_dump({"sets": [{"id": "default", "items": [{"id": "x", "prompt": "p"}]}]}),
            encoding="utf-8",
        )
        jobs = plan_jobs(load_manifest(mp), root=root)
        with pytest.raises(ValueError, match="SET/item"):
            filter_jobs(jobs, item_ref="nope")


def test_filter_char_id_sugar() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        mp = root / "m.yaml"
        mp.write_text(
            yaml.safe_dump(
                {
                    "sets": [
                        {"id": "char_priya", "items": [{"id": "idle", "prompt": "p"}]},
                        {"id": "default", "items": [{"id": "idle", "prompt": "d"}]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        jobs = plan_jobs(load_manifest(mp), root=root)
        f = filter_jobs(jobs, char_id="priya")
        assert len(f) == 1
        assert f[0].set_id == "char_priya"
