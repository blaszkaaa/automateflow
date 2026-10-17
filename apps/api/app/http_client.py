"""Constrained read-only HTTP client for demo workflows.

The user-controlled URL must use HTTPS and match an exact hostname allowlist.
No credentials, redirects, proxy discovery, custom ports or private IP literals.
"""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlsplit

import httpx

MAX_RESPONSE_BYTES = 16_000
DEFAULT_ALLOWED_HOSTS = "jsonplaceholder.typicode.com"


class HTTPRequestError(ValueError):
    """A request was denied, failed or exceeded the configured limits."""


def validated_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 2048:
        raise HTTPRequestError("Enter a valid HTTPS URL (maximum 2048 characters).")

    try:
        parts = urlsplit(url)
        hostname = (parts.hostname or "").lower()
        port = parts.port
    except ValueError as exc:
        raise HTTPRequestError("Invalid request URL.") from exc

    allowed = {host.strip().lower() for host in os.getenv(
        "HTTP_ALLOWED_HOSTS", DEFAULT_ALLOWED_HOSTS
    ).split(",") if host.strip()}

    if parts.scheme != "https" or not hostname or port not in (None, 443):
        raise HTTPRequestError("Only HTTPS URLs using the default port are permitted.")
    if parts.username is not None or parts.password is not None or parts.fragment:
        raise HTTPRequestError("Credentials and fragments are not permitted in request URLs.")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise HTTPRequestError("IP address URLs are not permitted.")
    if hostname not in allowed:
        raise HTTPRequestError(
            f"Host '{hostname}' is not allowed. Configure HTTP_ALLOWED_HOSTS on the server."
        )
    return url


def secure_http_get(url: str) -> str:
    url = validated_url(url)
    try:
        # Explicitly disable proxy environment variables and redirect following.
        with httpx.Client(timeout=6.0, follow_redirects=False, trust_env=False) as client:
            with client.stream("GET", url) as response:
                if response.is_redirect:
                    raise HTTPRequestError("Redirect responses are not supported.")
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise HTTPRequestError("The response exceeds the 16 KB limit.")
                return body.decode("utf-8", errors="replace")
    except httpx.HTTPError as exc:
        raise HTTPRequestError(f"HTTP request failed: {type(exc).__name__}") from exc
