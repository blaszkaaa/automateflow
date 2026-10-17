import pytest

from app.http_client import HTTPRequestError, validated_url


def test_https_allowed_host():
    assert validated_url("https://jsonplaceholder.typicode.com/todos/1").endswith("/todos/1")


@pytest.mark.parametrize("url", [
    "http://jsonplaceholder.typicode.com/todos/1",
    "https://127.0.0.1/private",
    "https://localhost/private",
    "https://jsonplaceholder.typicode.com:8080/data",
    "https://jsonplaceholder.typicode.com@127.0.0.1/data",
    "https://not-jsonplaceholder.typicode.com/data",
])
def test_rejects_untrusted_urls(url):
    with pytest.raises(HTTPRequestError):
        validated_url(url)


def test_custom_allowlist(monkeypatch):
    monkeypatch.setenv("HTTP_ALLOWED_HOSTS", "api.example.org,another.example.org")
    assert validated_url("https://api.example.org/v1") == "https://api.example.org/v1"
    with pytest.raises(HTTPRequestError):
        validated_url("https://jsonplaceholder.typicode.com")



def test_reject_redirect_without_contacting_target(monkeypatch):
    import httpx
    from app.http_client import secure_http_get

    original_client = httpx.Client

    def make_client(*args, **kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        transport = httpx.MockTransport(
            lambda request: httpx.Response(302, headers={"Location": "http://localhost/private"})
        )
        return original_client(transport=transport, **kwargs)

    monkeypatch.setattr("app.http_client.httpx.Client", make_client)
    with pytest.raises(HTTPRequestError, match="Redirect"):
        secure_http_get("https://jsonplaceholder.typicode.com/redirect")


def test_reject_oversized_response(monkeypatch):
    import httpx
    from app.http_client import secure_http_get

    original_client = httpx.Client

    def make_client(*args, **kwargs):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"x" * 4001)
        )
        return original_client(transport=transport, **kwargs)

    monkeypatch.setattr("app.http_client.httpx.Client", make_client)
    with pytest.raises(HTTPRequestError, match="exceeds"):
        secure_http_get("https://jsonplaceholder.typicode.com/large")
