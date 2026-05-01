"""Parallel batch and matrix (multi-variant) runs."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from harness.runner import (
    load_api_key,
    merge_coach_mode,
    load_preset_for_mode,
    prepare_named_run_dir,
    resolve_coach_preset_path,
    run_once,
    write_meta,
)
from harness.scenario import load_scenario


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", name.strip())
    return s.strip("_")[:64] or "variant"


def make_batch_root(out: Path) -> Path:
    bid = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    root = out / bid
    root.mkdir(parents=True, exist_ok=True)
    return root


def run_batch(
    scenario_dir: Path,
    *,
    out: Path,
    runs: int,
    agent_model: str,
    coach_model: str | None,
    concurrency: int = 3,
    seed_base: int | None = None,
    secrets: Path | None = None,
    batch_label: str = "batch",
    variant_name: str | None = None,
    coach_mode_cli: str | None = None,
    coach_preset_cli: Path | None = None,
    verbose: bool = False,
) -> Path:
    """Run the same scenario N times; returns batch directory path."""

    from harness.integrations.openrouter import OpenRouterClient

    coach_model = coach_model or agent_model
    batch_root = make_batch_root(out)
    bundle = load_scenario(scenario_dir)
    key = load_api_key(secrets)
    client = OpenRouterClient(api_key=key)

    manifest: dict[str, Any] = {
        "batch_id": batch_root.name,
        "scenario_dir": str(scenario_dir),
        "variant_name": variant_name,
        "agent_model": agent_model,
        "coach_model": coach_model,
        "coach_mode": merge_coach_mode(coach_mode_cli, bundle.scenario),
        "runs_requested": runs,
        "runs": [],
    }
    (batch_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def one(idx: int) -> dict[str, Any]:
        seed = None if seed_base is None else seed_base + idx
        run_name = f"{_slug(batch_label)}_{idx:03d}"
        run_root, rid = prepare_named_run_dir(batch_root, run_name)
        batch_mode = merge_coach_mode(coach_mode_cli, bundle.scenario)
        preset_path = resolve_coach_preset_path(coach_preset_cli, bundle)
        try:
            preset_data, preset_eff = load_preset_for_mode(batch_mode, preset_path)
        except ValueError as err:
            return {"run_id": rid, "path": run_name, "ok": False, "error": str(err)}
        extra: dict[str, Any] = {
            "coach_mode": batch_mode,
            "coach_preset_id": preset_data.get("id") if preset_data else None,
            "coach_preset_path": str(preset_eff) if preset_eff else None,
        }
        if variant_name:
            extra["variant_name"] = variant_name
        write_meta(
            run_root / "meta.yaml",
            bundle=bundle,
            agent_model=agent_model,
            coach_model=coach_model,
            seed=seed,
            run_id=rid,
            extra=extra,
        )
        try:
            summary = run_once(
                bundle,
                client,
                agent_model=agent_model,
                coach_model=coach_model,
                run_root=run_root,
                seed=seed,
                coach_mode=batch_mode,
                coach_preset=preset_data,
                coach_preset_source=preset_eff,
                verbose=verbose,
                progress_prefix=(
                    f"[{batch_root.name} {idx + 1}/{runs} {rid}] "
                    if verbose
                    else ""
                ),
            )
            return {"run_id": rid, "path": run_name, "ok": True, "summary": summary}
        except Exception as err:  # noqa: BLE001
            return {"run_id": rid, "path": run_name, "ok": False, "error": str(err)}

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futures = [ex.submit(one, i) for i in range(runs)]
        for fut in as_completed(futures):
            results.append(fut.result())

    manifest["runs"] = sorted(results, key=lambda r: r.get("path", ""))
    (batch_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return batch_root


def _path_relative_to_matrix(matrix_file: Path, rel: str | None) -> Path | None:
    if not rel:
        return None
    p = Path(str(rel))
    if p.is_absolute():
        return p.resolve()
    return (matrix_file.parent / p).resolve()


def run_matrix(
    matrix_path: Path,
    *,
    out: Path,
    scenario_override: Path | None,
    secrets: Path | None = None,
    verbose: bool = False,
) -> Path:
    """Load variants.yaml (or similar) and run each variant multiple times."""

    raw = yaml.safe_load(matrix_path.read_text(encoding="utf-8")) or {}
    if scenario_override is not None:
        scenario_dir = scenario_override.resolve()
    else:
        sd = raw.get("scenario_dir")
        if not sd:
            raise ValueError("matrix file must set 'scenario_dir' or pass --scenario")
        resolved = _path_relative_to_matrix(matrix_path, str(sd))
        if resolved is None:
            raise ValueError("matrix file scenario_dir is empty")
        scenario_dir = resolved
    runs_per = int(raw.get("runs_per_variant", 1))
    concurrency = int(raw.get("concurrency", 3))
    seed_base = raw.get("seed_base")
    if seed_base is not None:
        seed_base = int(seed_base)

    variants = list(raw.get("variants") or [])
    if not variants:
        raise ValueError("matrix file must list 'variants'")

    batch_root = make_batch_root(out)
    from harness.integrations.openrouter import OpenRouterClient

    bundle = load_scenario(scenario_dir)
    key = load_api_key(secrets)
    client = OpenRouterClient(api_key=key)

    manifest: dict[str, Any] = {
        "batch_id": batch_root.name,
        "matrix_file": str(matrix_path),
        "scenario_dir": str(scenario_dir),
        "variants": [],
    }

    tasks: list[tuple[str, int, str, str, int | None, str, Path | None]] = []
    for v in variants:
        name = str(v.get("name", "variant"))
        am = str(v["agent_model"])
        coach_m = str(v.get("coach_model") or am)
        cmode = str(v.get("coach_mode") or merge_coach_mode(None, bundle.scenario)).lower()
        cpath = _path_relative_to_matrix(matrix_path, v.get("coach_preset"))
        for i in range(runs_per):
            seed = None if seed_base is None else seed_base + len(tasks)
            tasks.append((name, i, am, coach_m, seed, cmode, cpath))

    results: list[dict[str, Any]] = []

    def work(item: tuple[str, int, str, str, int | None, str, Path | None]) -> dict[str, Any]:
        vname, idx, am, cm, seed, cmode, cpath_cli = item
        run_name = f"{_slug(vname)}_{idx:03d}"
        run_root, rid = prepare_named_run_dir(batch_root, run_name)
        try:
            preset_data, preset_eff = load_preset_for_mode(cmode, cpath_cli)
        except ValueError as err:
            return {
                "variant_name": vname,
                "run_index": idx,
                "run_id": rid,
                "path": run_name,
                "ok": False,
                "error": str(err),
            }
        extra = {
            "variant_name": vname,
            "coach_mode": cmode,
            "coach_preset_id": preset_data.get("id") if preset_data else None,
            "coach_preset_path": str(preset_eff) if preset_eff else None,
        }
        write_meta(
            run_root / "meta.yaml",
            bundle=bundle,
            agent_model=am,
            coach_model=cm,
            seed=seed,
            run_id=rid,
            extra=extra,
        )
        try:
            summary = run_once(
                bundle,
                client,
                agent_model=am,
                coach_model=cm,
                run_root=run_root,
                seed=seed,
                coach_mode=cmode,
                coach_preset=preset_data,
                coach_preset_source=preset_eff,
                verbose=verbose,
                progress_prefix=(
                    f"[{batch_root.name} {vname} #{idx + 1}/{runs_per} {rid}] "
                    if verbose
                    else ""
                ),
            )
            return {
                "variant_name": vname,
                "run_index": idx,
                "run_id": rid,
                "path": run_name,
                "ok": True,
                "summary": summary,
            }
        except Exception as err:  # noqa: BLE001
            return {
                "variant_name": vname,
                "run_index": idx,
                "run_id": rid,
                "path": run_name,
                "ok": False,
                "error": str(err),
            }

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futs = [ex.submit(work, t) for t in tasks]
        for fut in as_completed(futs):
            results.append(fut.result())

    manifest["runs"] = sorted(results, key=lambda r: (str(r.get("variant_name")), r.get("run_index", 0)))
    (batch_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return batch_root
