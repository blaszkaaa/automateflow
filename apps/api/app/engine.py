"""Small, deterministic executor for connected linear workflow graphs."""

from __future__ import annotations

from typing import Any

LABELS = {
    "start": "Start",
    "setText": "Set text",
    "uppercase": "Uppercase",
    "append": "Append text",
    "end": "End",
}
MAX_NODES = 25
MAX_TEXT = 4000


class InvalidWorkflow(ValueError):
    """Raised when the workflow topology or data is invalid."""


def execute_workflow(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    if not 2 <= len(nodes) <= MAX_NODES:
        raise InvalidWorkflow("A workflow must contain between 2 and 25 steps.")
    if len(edges) != len(nodes) - 1:
        raise InvalidWorkflow("Connect all steps in one linear sequence.")

    by_id: dict[str, dict[str, Any]] = {}
    starts: list[str] = []
    ends: list[str] = []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            raise InvalidWorkflow("Every step needs a valid ID.")
        node_id = node["id"]
        kind = node.get("data", {}).get("kind") if isinstance(node.get("data"), dict) else None
        if kind not in LABELS:
            raise InvalidWorkflow("Unsupported step type: " + str(kind))
        if node_id in by_id:
            raise InvalidWorkflow("Step IDs must be unique.")
        by_id[node_id] = node
        if kind == "start":
            starts.append(node_id)
        if kind == "end":
            ends.append(node_id)

    if len(starts) != 1 or len(ends) != 1:
        raise InvalidWorkflow("Exactly one Start and one End step are required.")

    successor: dict[str, str] = {}
    incoming: set[str] = set()
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if source not in by_id or target not in by_id or source == target:
            raise InvalidWorkflow("Invalid connection.")
        if source in successor or target in incoming:
            raise InvalidWorkflow("Only one incoming and outgoing connection per step is supported.")
        successor[source] = target
        incoming.add(target)

    if starts[0] in incoming or ends[0] in successor:
        raise InvalidWorkflow("Start must be first and End must be last.")

    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    current = starts[0]
    while current in by_id and current not in seen:
        seen.add(current)
        ordered.append(by_id[current])
        if current not in successor:
            break
        current = successor[current]

    if len(seen) != len(nodes) or ordered[-1]["id"] != ends[0]:
        raise InvalidWorkflow("The workflow contains a cycle or disconnected steps.")

    value = ""
    history: list[dict[str, str]] = []
    for node in ordered:
        data = node["data"]
        kind = data["kind"]
        before = value
        argument = data.get("value", "")
        if kind in ("setText", "append"):
            if not isinstance(argument, str) or len(argument) > MAX_TEXT:
                raise InvalidWorkflow("Step text must be at most 4000 characters.")
        if kind == "setText":
            value = argument
        elif kind == "uppercase":
            value = value.upper()
        elif kind == "append":
            value += argument
        if len(value) > MAX_TEXT:
            raise InvalidWorkflow("Output exceeds 4000 characters.")
        history.append(
            {"node_id": node["id"], "label": LABELS[kind], "input": before, "output": value, "status": "success"}
        )

    return {"output": value, "steps": history}
