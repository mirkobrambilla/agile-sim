"""Pydantic schemas for structured LLM outputs (harness v1)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChannelPost(BaseModel):
    channel: str
    content: str
    parent_id: str | None = None


class AgentTurnOutput(BaseModel):
    narrative: str = ""
    channel_posts: list[ChannelPost] = Field(default_factory=list)
    process_invocations: list[dict[str, Any]] = Field(
        default_factory=list,
        description='Optional process hooks, e.g. {"kind": "consult", "topic": "architecture"}.',
    )
    vital_self_report: dict[str, int] = Field(
        default_factory=dict,
        description="Per-vital deltas for this character (bounded by harness).",
    )
    work_item_updates: list[dict[str, Any]] = Field(
        default_factory=list,
        description='Items: {"id": "W1", "state": "backlog"|"doing"|"done"}',
    )


class CoachTurnOutput(BaseModel):
    narrative: str = ""
    channel_posts: list[ChannelPost] = Field(default_factory=list)
    process_invocations: list[dict[str, Any]] = Field(
        default_factory=list,
        description='Process moves, e.g. {"kind": "request_approval", "gate": "release"}.',
    )
    vital_nudges: list[dict[str, Any]] = Field(
        default_factory=list,
        description='Items: {"character_id": "priya", "vital_name": "stress", "delta": -5}',
    )
