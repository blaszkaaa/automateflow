"""Minimal, restricted Playwright session for short, allowlisted demo workflows.

Only user-selected HTTPS hosts are reachable by browser requests. Requests are
fetched without following redirects and explicitly fulfilled; all other hosts,
unsafe methods and WebSockets are denied. This is defense in depth, not a
substitute for network isolation or authentication in multi-tenant deployments.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from .http_client import HTTPRequestError, validated_url


class BrowserStepError(ValueError):
    """A browser action was denied or could not complete."""


ALLOWED_KEYS = {"Enter", "Tab", "Escape", "Space", "ArrowDown", "ArrowUp"}
STEP_TIMEOUT_MS = 5000
MAX_ACTION_TEXT = 1000
MAX_SELECTOR = 200


def check_browser_url(url: str) -> str:
    hosts = os.getenv("BROWSER_ALLOWED_HOSTS", "demo.playwright.dev")
    try:
        return validated_url(url, allowed_hosts=hosts)
    except HTTPRequestError as exc:
        raise BrowserStepError(str(exc)) from exc


def check_selector(selector: Any) -> str:
    if not isinstance(selector, str) or not 1 <= len(selector) <= MAX_SELECTOR:
        raise BrowserStepError("Provide a CSS selector (1–200 characters).")
    # Only CSS selectors: prevent Playwright's built-in alternative selector engines.
    if ">>" in selector or selector.startswith(("xpath=", "text=", "role=", "id=", "data-testid=")):
        raise BrowserStepError("Only CSS selectors are supported.")
    return selector


class BrowserSession:
    """A fresh, disposable headless Chromium tab shared by browser steps in one run."""

    def __init__(self) -> None:
        self._manager: Any = None
        self.browser: Any = None
        self.context: Any = None
        self.page: Any = None

    def __enter__(self) -> "BrowserSession":
        try:
            self._manager = sync_playwright().start()
            self.browser = self._manager.chromium.launch(headless=True)
            self.context = self.browser.new_context(
                service_workers="block",
                accept_downloads=False,
                permissions=[],
            )
            self.context.route("**/*", self._route_request)
            # Prevent off-list socket connections (not covered by HTTP routing).
            self.context.route_web_socket("**/*", lambda socket: socket.close())
            self.page = self.context.new_page()
            self.page.set_default_timeout(STEP_TIMEOUT_MS)
            self.page.set_default_navigation_timeout(10_000)
            return self
        except Exception as exc:
            self.__exit__(None, None, None)
            raise BrowserStepError("Unable to launch Chromium for this workflow.") from exc

    def __exit__(self, *_: Any) -> None:
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
        finally:
            if self._manager:
                self._manager.stop()

    @staticmethod
    def _route_request(route: Any) -> None:
        try:
            check_browser_url(route.request.url)
            if route.request.method not in ("GET", "HEAD"):
                route.abort()
                return
            # route.continue_() silently follows redirects without a second route
            # interception; max_redirects=0 + fulfill avoids this bypass.
            response = route.fetch(max_redirects=0, timeout=10_000)
            if 300 <= response.status < 400:
                route.fulfill(status=403, body="Redirects are disabled.")
            else:
                route.fulfill(response=response)
        except (HTTPRequestError, BrowserStepError, PlaywrightError, ValueError):
            try:
                route.abort()
            except PlaywrightError:
                pass

    def navigate(self, url: str) -> str:
        url = check_browser_url(url)
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=10_000)
            # Record the final URL, but never permit off-list navigation.
            check_browser_url(self.page.url)
        except (PlaywrightError, BrowserStepError) as exc:
            raise BrowserStepError("Page navigation failed or was blocked.") from exc
        return "Opened " + self.page.url

    def fill(self, selector: str, text: str) -> str:
        selector = check_selector(selector)
        if not isinstance(text, str) or len(text) > MAX_ACTION_TEXT:
            raise BrowserStepError("Text must be at most 1,000 characters.")
        self._action(lambda: self.page.locator(selector).fill(text))
        return text

    def click(self, selector: str) -> str:
        selector = check_selector(selector)
        self._action(lambda: self.page.locator(selector).click())
        return "Clicked " + selector

    def press(self, selector: str, key: str) -> str:
        selector = check_selector(selector)
        if key not in ALLOWED_KEYS:
            raise BrowserStepError("The requested key is not allowed.")
        self._action(lambda: self.page.locator(selector).press(key))
        return "Pressed " + key + " on " + selector

    def read_text(self, selector: str) -> str:
        selector = check_selector(selector)
        value = self._action(lambda: self.page.locator(selector).first.inner_text())
        return str(value).strip()[:4000]

    @staticmethod
    def _action(action: Any) -> Any:
        try:
            return action()
        except PlaywrightError as exc:
            raise BrowserStepError("Browser action failed: element not found, blocked or timed out.") from exc
