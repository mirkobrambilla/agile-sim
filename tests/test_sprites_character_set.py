from __future__ import annotations

from pathlib import Path

from harness.web.sprites import character_sprite_set


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n")


def test_character_sprite_set_prefers_explicit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("harness.web.sprites.repo_root", lambda: tmp_path)
    _touch(tmp_path / "harness" / "web" / "static" / "sprites" / "char_alex" / "idle.png")
    scenario = {"characters": [{"id": "alex", "sprite_set": "team_alex"}]}
    assert character_sprite_set(scenario, "alex") == "team_alex"


def test_character_sprite_set_uses_char_folder_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("harness.web.sprites.repo_root", lambda: tmp_path)
    _touch(tmp_path / "harness" / "web" / "static" / "sprites" / "char_sam" / "idle.png")
    scenario = {"characters": [{"id": "sam"}]}
    assert character_sprite_set(scenario, "sam") == "char_sam"


def test_character_sprite_set_defaults_when_unknown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("harness.web.sprites.repo_root", lambda: tmp_path)
    scenario = {"characters": [{"id": "riley"}]}
    assert character_sprite_set(scenario, "riley") == "default"
