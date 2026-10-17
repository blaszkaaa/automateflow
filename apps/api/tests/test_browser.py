"""Browser RPA tests are deterministic: no external websites or browser downloads."""

from types import SimpleNamespace

import pytest

from app.browser import BrowserSession, BrowserStepError, check_browser_url
from app.engine import execute_workflow


def graph(kinds, config=None):
    config = config or {}
    return (
        [{"id": str(i), "data": {"kind": kind, **config.get(i, {})}} for i, kind in enumerate(kinds)],
        [{"source": str(i), "target": str(i + 1)} for i in range(len(kinds) - 1)],
    )


class FakeBrowser:
    def __init__(self):
        self.actions = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def navigate(self, url):
        self.actions.append(("navigate", url))
        return "Opened " + url

    def fill(self, selector, text):
        self.actions.append(("fill", selector, text))
        return text

    def click(self, selector):
        self.actions.append(("click", selector))
        return "Clicked " + selector

    def press(self, selector, key):
        self.actions.append(("press", selector, key))
        return "Pressed " + key + " on " + selector

    def read_text(self, selector):
        self.actions.append(("read", selector))
        return "Prepare portfolio demo"


def test_full_browser_workflow_and_session_cleanup():
    kinds = ["start", "browserNavigate", "browserFill", "browserPress", "browserRead", "end"]
    cfg = {
        1: {"value": "https://demo.playwright.dev/todomvc/"},
        2: {"selector": ".new-todo", "text": "Prepare portfolio demo"},
        3: {"selector": ".new-todo", "key": "Enter"},
        4: {"selector": ".todo-list li"},
    }
    nodes, edges = graph(kinds, cfg)
    fake = FakeBrowser()
    result = execute_workflow(nodes, edges, browser_factory=lambda: fake)
    assert result["status"] == "success"
    assert result["output"] == "Prepare portfolio demo"
    assert len(result["steps"]) == 6
    assert fake.actions == [
        ("navigate", "https://demo.playwright.dev/todomvc/"),
        ("fill", ".new-todo", "Prepare portfolio demo"),
        ("press", ".new-todo", "Enter"),
        ("read", ".todo-list li"),
    ]
    assert fake.closed


def test_click_action_and_cleanup_on_failure():
    nodes, edges = graph(
        ["start", "browserNavigate", "browserClick", "end"],
        {1: {"value": "https://demo.playwright.dev/todomvc/"},
         2: {"selector": ".toggle"}},
    )
    fake = FakeBrowser()
    result = execute_workflow(nodes, edges, browser_factory=lambda: fake)
    assert result["status"] == "success"
    assert ("click", ".toggle") in fake.actions
    assert fake.closed


def test_action_without_navigation_fails_in_trace():
    nodes, edges = graph(["start", "browserRead", "end"], {1: {"selector": "#title"}})
    result = execute_workflow(nodes, edges, browser_factory=lambda: pytest.fail("Must not launch"))
    assert result["status"] == "failed"
    assert "Open page" in result["steps"][-1]["error"]


def test_browser_closes_on_failed_step():
    class FailingBrowser(FakeBrowser):
        def click(self, selector):
            raise BrowserStepError("Element timed out")

    nodes, edges = graph(["start", "browserNavigate", "browserClick", "end"], {
        1: {"value": "https://demo.playwright.dev/todomvc/"},
        2: {"selector": ".missing"},
    })
    browser = FailingBrowser()
    result = execute_workflow(nodes, edges, browser_factory=lambda: browser)
    assert result["status"] == "failed"
    assert result["steps"][-1]["error"] == "Element timed out"
    assert browser.closed


@pytest.mark.parametrize("url", [
    "http://demo.playwright.dev/todomvc/",
    "https://localhost:443/private",
    "https://127.0.0.1/private",
    "https://demo.playwright.dev.evil.example/",
    "https://demo.playwright.dev:444/todomvc/",
    "https://someone:password@demo.playwright.dev/",
    "https://jsonplaceholder.typicode.com/",
])
def test_browser_rejects_non_allowlisted_urls(url):
    with pytest.raises(BrowserStepError):
        check_browser_url(url)


def test_browser_can_allow_explicit_hosts(monkeypatch):
    monkeypatch.setenv("BROWSER_ALLOWED_HOSTS", "docs.example.org")
    assert check_browser_url("https://docs.example.org/start") == "https://docs.example.org/start"
    with pytest.raises(BrowserStepError):
        check_browser_url("https://demo.playwright.dev")


class FakeRoute:
    def __init__(self, url="https://demo.playwright.dev/todomvc/", method="GET", status=200):
        self.request = SimpleNamespace(url=url, method=method)
        self.status = status
        self.calls = []

    def abort(self):
        self.calls.append(("abort",))

    def fetch(self, **kwargs):
        self.calls.append(("fetch", kwargs))
        return SimpleNamespace(status=self.status)

    def fulfill(self, **kwargs):
        self.calls.append(("fulfill", kwargs))


def test_network_guard_requires_allowlist_and_refuses_redirects():
    for route in [
        FakeRoute(url="https://127.0.0.1/secrets"),
        FakeRoute(method="POST"),
    ]:
        BrowserSession._route_request(route)
        assert route.calls == [("abort",)]

    redirect = FakeRoute(status=302)
    BrowserSession._route_request(redirect)
    assert redirect.calls[0] == ("fetch", {"max_redirects": 0, "timeout": 10_000})
    assert redirect.calls[1][0] == "fulfill"
    assert redirect.calls[1][1]["status"] == 403

    allowed = FakeRoute()
    BrowserSession._route_request(allowed)
    assert allowed.calls[0][1]["max_redirects"] == 0
    assert allowed.calls[1][1].get("response") is not None
