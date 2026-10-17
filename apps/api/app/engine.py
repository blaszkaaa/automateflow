"""Validated linear workflow runner with inspectable success/failure traces."""

from __future__ import annotations

import json
from contextlib import ExitStack
from typing import Any, Callable

from .browser import BrowserSession, BrowserStepError
from .http_client import HTTPRequestError, secure_http_get

LABELS = {
    "start": "Start",
    "setText": "Set text",
    "uppercase": "Uppercase",
    "append": "Append text",
    "httpGet": "HTTP GET",
    "jsonField": "Extract JSON field",
    "browserNavigate": "Open page",
    "browserClick": "Click element",
    "browserFill": "Fill input",
    "browserPress": "Press key",
    "browserRead": "Read page text",
    "end": "End",
}
MAX_NODES = 25
MAX_TEXT = 4000


class InvalidWorkflow(ValueError):
    """A graph or a step setting is invalid."""


class StepExecutionError(ValueError):
    """A workflow step is configured incorrectly."""


def extract_json_field(text: str, path: str) -> str:
    if not path or len(path) > 250 or not all(part and part != ".." for part in path.split(".")):
        raise StepExecutionError("Enter a dot-separated JSON path, e.g. user.name.")
    try:
        current: Any = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise StepExecutionError("Input is not valid JSON.") from exc
    for key in path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list) and key.isdecimal() and int(key) < len(current):
            current = current[int(key)]
        else:
            raise StepExecutionError(f"JSON path not found: {path}")
    if isinstance(current, str):
        return current
    return json.dumps(current, ensure_ascii=False, separators=(",", ":"))


def ordered_nodes(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not 2 <= len(nodes) <= MAX_NODES:
        raise InvalidWorkflow("A workflow must contain between 2 and 25 steps.")
    if len(edges) != len(nodes) - 1:
        raise InvalidWorkflow("Connect all steps in one linear sequence.")

    by_id: dict[str, dict[str, Any]] = {}
    starts: list[str] = []
    ends: list[str] = []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"]:
            raise InvalidWorkflow("Every step needs a valid ID.")
        data = node.get("data")
        kind = data.get("kind") if isinstance(data, dict) else None
        if kind not in LABELS:
            raise InvalidWorkflow("Unsupported step type: " + str(kind))
        node_id = node["id"]
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
        if not isinstance(edge, dict):
            raise InvalidWorkflow("Invalid connection.")
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
    return ordered


def execute_workflow(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    http_get: Callable[[str], str] = secure_http_get,
    browser_factory: Callable[[], BrowserSession] = BrowserSession,
) -> dict[str, Any]:
    ordered = ordered_nodes(nodes, edges)
    value = ""
    history: list[dict[str, str]] = []
    browser: BrowserSession | None = None

    # Browser is started only if a Navigate step occurs, and always closed.
    with ExitStack() as resources:
        for node in ordered:
            data = node["data"]
            kind = data["kind"]
            before = value
            argument = data.get("value", "")
            try:
                if kind in ("setText", "append", "httpGet", "jsonField", "browserNavigate"):
                    limit = 2048 if kind in ("httpGet", "browserNavigate") else MAX_TEXT
                    if not isinstance(argument, str) or len(argument) > limit:
                        raise StepExecutionError("Invalid step configuration.")
                if kind == "setText":
                    value = argument
                elif kind == "uppercase":
                    value = value.upper()
                elif kind == "append":
                    value += argument
                elif kind == "httpGet":
                    value = http_get(argument)
                elif kind == "jsonField":
                    value = extract_json_field(value, argument)
                elif kind == "browserNavigate":
                    if browser is None:
                        browser = resources.enter_context(browser_factory())
                    value = browser.navigate(argument)
                elif kind in ("browserClick", "browserFill", "browserPress", "browserRead"):
                    if browser is None:
                        raise StepExecutionError("Add an Open page step before browser actions.")
                    selector = data.get("selector", "")
                    if kind == "browserClick":
                        value = browser.click(selector)
                    elif kind == "browserFill":
                        value = browser.fill(selector, data.get("text", ""))
                    elif kind == "browserPress":
                        value = browser.press(selector, data.get("key", "Enter"))
                    else:
                        value = browser.read_text(selector)
                if len(value) > MAX_TEXT:
                    raise StepExecutionError("Output exceeds 4,000 characters.")
            except (StepExecutionError, HTTPRequestError, BrowserStepError, ValueError) as exc:
                history.append({
                    "node_id": node["id"], "label": LABELS[kind], "input": before,
                    "output": "", "status": "failed", "error": str(exc),
                })
                return {"status": "failed", "output": before, "steps": history}
            history.append({
                "node_id": node["id"], "label": LABELS[kind],
                "input": before, "output": value, "status": "success",
            })
    return {"status": "success", "output": value, "steps": history}
