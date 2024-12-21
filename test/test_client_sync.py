import ssl
from contextlib import contextmanager
from unittest.mock import MagicMock, call, patch

import httpx
import pytest

from reachable.client import Client


@pytest.fixture
def httpx_mock_client():
    """
    Fixture to create a mock of `httpx.Client`.
    """
    with patch("httpx.Client", autospec=True) as mock_class:
        yield mock_class


def test_init():
    """
    Test that the Client initializes an httpx.Client with expected params.
    """
    c = Client()

    assert c._type == "classic"
    assert c.timeout == 10

    assert "User-Agent" in c.headers
    assert "Accept" in c.headers
    assert "Accept-Language" in c.headers

    assert c.headers["Connection"] == "keep-alive"
    assert c.include_host is False
    assert c.ssl_fallback_to_http is False
    assert c.ensure_protocol_url is False
    assert c.timeout == 10
    c.close()


def test_request_success(httpx_mock_client):
    """
    Test a simple request call with no SSL error or fallback.
    """
    # Mock the client instance's request method
    mock_instance = httpx_mock_client.return_value
    mock_response = MagicMock(spec=httpx.Response, status_code=200)
    mock_instance.request.return_value = mock_response

    c = Client()
    resp = c.request("get", "https://example.com")

    assert resp.status_code == 200
    mock_instance.request.assert_called_with(
        "get",
        "https://example.com",
        headers=None,
        content=None,
    )
    c.close()


def test_request_ssl_error_with_fallback(httpx_mock_client):
    """
    Test that on an ssl.SSLError, we retry with HTTP if ssl_fallback_to_http is set.
    """
    mock_instance = httpx_mock_client.return_value
    # First call raises an SSLError, second call returns a valid response
    mock_instance.request.side_effect = [
        ssl.SSLError("SSL error"),
        MagicMock(spec=httpx.Response, status_code=200),
    ]

    c = Client(ssl_fallback_to_http=True)
    resp = c.request("get", "https://example.com")

    # Check that it attempted to make the request with http fallback
    calls = mock_instance.request.mock_calls
    assert len(calls) == 2
    assert calls[0] == call("get", "https://example.com", headers=None, content=None)
    # On fallback, it replaced https:// with http://
    assert calls[1] == call("get", "http://example.com", headers=None, content=None)
    assert resp.status_code == 200
    c.close()


def test_request_ssl_error_no_fallback(httpx_mock_client):
    """
    Test that on an ssl.SSLError, if fallback is NOT set, we re-raise the exception.
    """
    mock_instance = httpx_mock_client.return_value
    mock_instance.request.side_effect = ssl.SSLError("SSL error")

    c = Client(ssl_fallback_to_http=False)
    with pytest.raises(ssl.SSLError):
        c.request("get", "https://example.com")
    c.close()


def test_get(httpx_mock_client):
    """
    Test the 'get' convenience method.
    """
    mock_instance = httpx_mock_client.return_value
    mock_response = MagicMock(spec=httpx.Response, status_code=200)
    mock_instance.request.return_value = mock_response

    c = Client()
    resp = c.get("https://example.com")
    assert resp.status_code == 200
    mock_instance.request.assert_called_with(
        "get", "https://example.com", headers=None, content=None
    )
    c.close()


def test_post(httpx_mock_client):
    """
    Test the 'post' convenience method.
    """
    mock_instance = httpx_mock_client.return_value
    mock_response = MagicMock(spec=httpx.Response, status_code=201)
    mock_instance.request.return_value = mock_response

    c = Client()
    resp = c.post("https://example.com", content="some data")
    assert resp.status_code == 201
    mock_instance.request.assert_called_with(
        "post", "https://example.com", headers=None, content="some data"
    )
    c.close()


def test_head(httpx_mock_client):
    """
    Test the 'head' convenience method.
    """
    mock_instance = httpx_mock_client.return_value
    mock_response = MagicMock(spec=httpx.Response, status_code=200)
    mock_instance.request.return_value = mock_response

    c = Client()
    resp = c.head("https://example.com")
    assert resp.status_code == 200
    mock_instance.request.assert_called_with(
        "head", "https://example.com", headers=None, content=None
    )
    c.close()


def test_stream(httpx_mock_client):
    """
    Test that the stream method yields a response and also handles fallback if needed.
    """
    client = Client()
    # We manually set `client.client` to a mock so we can control `.stream(...)`
    client.client = httpx_mock_client

    @contextmanager
    def mock_stream_cm(*args, **kwargs):
        yield MagicMock(spec=httpx.Response)

    # When `client.client.stream(...)` is called, return our fake ACM
    httpx_mock_client.stream.side_effect = mock_stream_cm

    # Now call `.stream(...)`
    stream_ctx = client.stream("GET", "https://example.com")
    # Make sure it's an async context manager
    assert hasattr(stream_ctx, "__enter__") and hasattr(stream_ctx, "__exit__")

    # Check usage in an async with:
    with stream_ctx as response:
        assert isinstance(response, httpx.Response)
    # Verify we called `client.client.stream` with correct args
    client.client.stream.assert_called_once_with(
        "GET", "https://example.com", headers=None, content=None
    )


def test_close(httpx_mock_client):
    """
    Test the close method calls client.close().
    """
    mock_instance = httpx_mock_client.return_value
    c = Client()
    c.close()
    mock_instance.close.assert_called_once()
