import pytest

from app.engine import InvalidWorkflow, execute_workflow, extract_json_field


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
    assert result["status"] == "success"
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
    nodes[1]["data"]["value"] = "a" * 16000
    result = execute_workflow(nodes, edges)
    assert result["status"] == "failed"
    assert result["steps"][-1]["status"] == "failed"


def test_http_get_with_json_extraction():
    nodes, edges = workflow(["start", "httpGet", "jsonField", "uppercase", "end"])
    nodes[1]["data"]["value"] = "https://jsonplaceholder.typicode.com/todos/1"
    nodes[2]["data"]["value"] = "title"

    urls = []
    def fake_get(url):
        urls.append(url)
        return '{"userId":1,"title":"hello workflow"}'

    result = execute_workflow(nodes, edges, http_get=fake_get)
    assert urls == ["https://jsonplaceholder.typicode.com/todos/1"]
    assert result["output"] == "HELLO WORKFLOW"
    assert result["status"] == "success"
    assert result["steps"][2]["output"] == "hello workflow"


def test_http_error_is_a_persistable_failed_run():
    nodes, edges = workflow(["start", "httpGet", "end"])
    nodes[1]["data"]["value"] = "https://jsonplaceholder.typicode.com"
    def bad_get(_):
        raise ValueError("Service unavailable")
    result = execute_workflow(nodes, edges, http_get=bad_get)
    assert result["status"] == "failed"
    assert result["steps"][-1]["error"] == "Service unavailable"
    assert len(result["steps"]) == 2


def test_json_nested_fields_and_array_indices():
    assert extract_json_field('{"a":{"items":[{"id":42}]}}', "a.items.0.id") == "42"


def test_json_missing_field_shows_useful_message():
    nodes, edges = workflow(["start", "setText", "jsonField", "end"])
    nodes[1]["data"]["value"] = '{"ok":true}'
    nodes[2]["data"]["value"] = "user.email"
    result = execute_workflow(nodes, edges)
    assert result["status"] == "failed"
    assert "JSON path not found" in result["steps"][-1]["error"]
