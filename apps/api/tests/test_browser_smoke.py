"""Headless Chromium smoke test using a synthetic HTTPS page, no internet needed."""

from app.browser import BrowserSession
from app.engine import execute_workflow


def test_chromium_executes_form_automation(monkeypatch):
    html = """
    <!doctype html><html><body>
      <input class="new-todo" aria-label="Add todo"/>
      <ul class="todo-list"></ul>
      <script>
        const input = document.querySelector(".new-todo");
        input.addEventListener("keydown", (event) => {
          if (event.key === "Enter" && input.value.trim()) {
            const item = document.createElement("li");
            item.textContent = input.value;
            document.querySelector(".todo-list").appendChild(item);
          }
        });
      </script>
    </body></html>
    """

    def serve_local_fixture(route):
        if route.request.url == "https://demo.playwright.dev/todomvc/":
            route.fulfill(status=200, content_type="text/html", body=html)
        else:
            route.abort()

    monkeypatch.setattr(BrowserSession, "_route_request", staticmethod(serve_local_fixture))

    kinds = ["start", "browserNavigate", "browserFill", "browserPress", "browserRead", "end"]
    args = {
        1: {"value": "https://demo.playwright.dev/todomvc/"},
        2: {"selector": ".new-todo", "text": "Real Chromium works"},
        3: {"selector": ".new-todo", "key": "Enter"},
        4: {"selector": ".todo-list li"},
    }
    nodes = [{"id": str(i), "data": {"kind": kind, **args.get(i, {})}}
             for i, kind in enumerate(kinds)]
    edges = [{"source": str(i), "target": str(i + 1)}
             for i in range(len(kinds) - 1)]
    result = execute_workflow(nodes, edges)
    assert result["status"] == "success", result["steps"]
    assert result["output"] == "Real Chromium works"
    assert len(result["steps"]) == len(kinds)
