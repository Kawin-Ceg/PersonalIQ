"""Shared state passed through the workflow graph."""

from typing import Annotated, Any, TypedDict


def merge(left: dict | None, right: dict | None) -> dict:
    """Reducer: parallel agents each add their own key, so results are merged, not overwritten."""
    return {**(left or {}), **(right or {})}


class PersonalIQState(TypedDict, total=False):
    workflow_id: str
    user_id: str
    started_at: str  # ISO time; the supervisor stops routing to agents once the time limit is used up
    intent: dict[str, Any]
    # agent key -> AgentResult as JSON. Written by every node, merged by the reducer.
    runs: Annotated[dict[str, Any], merge]
    # Supervisor recovery: {"tried": [strategy, ...], "budget": "<override>", "depth": <candidates per need>}
    recovery: dict[str, Any]
    outcome: dict[str, Any]
