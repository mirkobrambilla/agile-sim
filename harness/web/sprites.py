"""Sprite URLs and expression mapping for the web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sprite_png_exists(set_id: str, expression: str) -> bool:
    p = repo_root() / "harness" / "web" / "static" / "sprites" / set_id
    if not p.is_dir():
        return False
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        if (p / f"{expression}{ext}").is_file():
            return True
    return False


def sprite_url(set_id: str, expression: str) -> str | None:
    base = repo_root() / "harness" / "web" / "static" / "sprites" / set_id
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        f = base / f"{expression}{ext}"
        if f.is_file():
            return f"/static/sprites/{set_id}/{expression}{ext}"
    return None


def expression_from_vitals(vitals: dict[str, Any]) -> str:
    """Map ledger vitals to sprite expression id (matches assets/manifest default set)."""

    try:
        stress = int(vitals.get("stress") or 0)
        mot = int(vitals.get("motivation") or 5)
        energy = int(vitals.get("energy") or 5)
    except (TypeError, ValueError):
        return "idle"
    if stress >= 9:
        return "overloaded"
    if stress >= 6:
        return "frustrated"
    if mot <= 2:
        return "bored"
    if energy <= 2 and stress >= 4:
        return "sad"
    return "idle"


def character_meta_by_id(scenario: dict[str, Any]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for c in scenario.get("characters") or []:
        cid = str(c.get("id", "")).strip()
        if not cid:
            continue
        handle = f"@{cid}"
        name = str(c.get("name") or cid).strip()
        out[cid] = {"name": name, "handle": handle}
    return out
