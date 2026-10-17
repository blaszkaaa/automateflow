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
