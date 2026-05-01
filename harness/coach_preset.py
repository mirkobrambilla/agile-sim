"""Pre-written coach turns (YAML) for A/B comparisons against LLM or no coach."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from harness.schemas import ChannelPost, CoachTurnOutput


def load_coach_preset(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("coach preset root must be a mapping")
    return data


def _turn_block(preset: dict[str, Any], turn: int) -> dict[str, Any] | None:
    turns = preset.get("turns")
    if turns is None:
        return None
    if isinstance(turns, list):
        for blk in turns:
            if isinstance(blk, dict) and int(blk.get("turn", -1)) == turn:
                return blk
        return None
    if isinstance(turns, dict):
        return turns.get(str(turn)) or turns.get(turn)
    return None


def coach_turn_from_preset(
    preset: dict[str, Any],
    turn: int,
    *,
    default_channel: str,
) -> CoachTurnOutput:
    block = _turn_block(preset, turn)
    if not block:
        return CoachTurnOutput(
            narrative=f"(preset: no entry for turn {turn})",
        )
    posts: list[ChannelPost] = []
    for raw in block.get("channel_posts") or []:
        if isinstance(raw, str):
            posts.append(ChannelPost(channel=default_channel, content=raw))
        elif isinstance(raw, dict):
            ch = str(raw.get("channel") or default_channel)
            body = str(raw.get("content", ""))
            if body.strip():
                posts.append(
                    ChannelPost(
                        channel=ch,
                        content=body,
                        parent_id=raw.get("parent_id"),
                    )
                )
    nudges: list[dict[str, Any]] = []
    for n in block.get("vital_nudges") or []:
        if isinstance(n, dict):
            nudges.append(dict(n))
    return CoachTurnOutput(
        narrative=str(block.get("narrative") or ""),
        channel_posts=posts,
        vital_nudges=nudges,
    )
