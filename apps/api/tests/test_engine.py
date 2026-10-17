import pytest

from app.engine import InvalidWorkflow, execute_workflow


def workflow(kinds):
    nodes = [
        {"id": str(i), "data": {"kind": kind, "value": "hello" if kind == "setText" else "!"}}
        for i, kind in enumerate(kinds)
    ]
    edges = [
        {"source": str(i), "target": str(i + 1)}
        for i in range(len(kinds) - 1)
    ]
    return nodes, edges


def test_execute_linear_workflow():
    nodes, edges = workflow(["start", "setText", "uppercase", "append", "end"])
    result = execute_workflow(nodes, edges)
    assert result["output"] == "HELLO!"
    assert len(result["steps"]) == 5
    assert result["steps"][2]["input"] == "hello"


def test_requires_connected_workflow():
    nodes, edges = workflow(["start", "setText", "end"])
    with pytest.raises(InvalidWorkflow):
        execute_workflow(nodes, edges[:-1])


def test_rejects_unknown_step():
    nodes, edges = workflow(["start", "python", "end"])
    with pytest.raises(InvalidWorkflow, match="Unsupported"):
        execute_workflow(nodes, edges)


def test_rejects_duplicate_nodes():
    nodes, edges = workflow(["start", "setText", "end"])
    nodes[1]["id"] = "0"
    with pytest.raises(InvalidWorkflow, match="unique"):
        execute_workflow(nodes, edges)


def test_rejects_cycles():
    nodes, edges = workflow(["start", "setText", "end"])
    edges = [{"source": "0", "target": "1"}, {"source": "1", "target": "0"}]
    with pytest.raises(InvalidWorkflow):
        execute_workflow(nodes, edges)


def test_limits_output_size():
    nodes, edges = workflow(["start", "setText", "append", "end"])
    nodes[1]["data"]["value"] = "a" * 4000
    with pytest.raises(InvalidWorkflow, match="exceeds"):
        execute_workflow(nodes, edges)
