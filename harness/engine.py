"""Process / org mechanics hook (v1): records structured invocations from agents and coach."""

from __future__ import annotations

from typing import Any

from harness.scenario import ScenarioBundle
from harness.world import World

_HANDLED = frozenset(
    {
        "consult",
        "invoke",
        "tick",
        "request_approval",
        "change_deadline",
        "edit_ritual",
        "set_gate",
    }
)


def tick(world: World, bundle: ScenarioBundle) -> list[dict[str, Any]]:
    """Called at the start of each simulation turn; emit timeline rows when mechanics apply."""

    _ = world, bundle
    return []


def apply_process_invocations(
    invocations: list[dict[str, Any]] | None,
    *,
    world: World,
    bundle: ScenarioBundle,
    source: str,
    turn: int,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    _ = world
    for inv in invocations or []:
        kind = str(inv.get("kind", "")).strip().lower()
        if kind in _HANDLED:
            events.append(
                {
                    "kind": "process_invocation",
                    "turn": turn,
                    "source": source,
                    "process_kind": kind,
                    "invocation": inv,
                    "scenario_id": bundle.scenario.get("id"),
                }
            )
        elif kind:
            events.append(
                {
                    "kind": "process_invocation_unhandled",
                    "turn": turn,
                    "source": source,
                    "invocation": inv,
                }
            )
    return events
