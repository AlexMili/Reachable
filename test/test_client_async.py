import ssl
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from reachable.client import AsyncClient


@pytest.fixture
def async_mock_client():
    with patch("httpx.AsyncClient", autospec=True) as mock_class:
        yield mock_class


@pytest.mark.asyncio
async def test_init(async_mock_client):
    c = AsyncClient()

    # Must call open() to create self.client
    await c.open()
    assert c._type == "classic"

    async_mock_client.assert_called_once()
    called_args, called_kwargs = async_mock_client.call_args

    assert called_kwargs["timeout"] == 10
    assert called_kwargs["http2"] is True

    await c.close()


@pytest.mark.asyncio
async def test_context_manager(async_mock_client):
    """
    Test usage of the async context manager.
    """
    async with AsyncClient() as c:
        assert c.client is not None
    # The above should call open() then close().


@pytest.mark.asyncio
async def test_request_success(async_mock_client):
    mock_instance = async_mock_client.return_value
    mock_response = MagicMock(spec=httpx.Response, status_code=200)
    mock_instance.request = AsyncMock(return_value=mock_response)

    c = AsyncClient()
    await c.open()

    resp = await c.request("get", "https://example.com")
    assert resp.status_code == 200

    mock_instance.request.assert_called_with(
        "get",
        "https://example.com",
        headers=None,
        content=None,
    )
    await c.close()


@pytest.mark.asyncio
async def test_request_ssl_error_with_fallback(async_mock_client):
    mock_instance = async_mock_client.return_value
    mock_instance.request = AsyncMock(
        side_effect=[
            ssl.SSLError("SSL error"),
            MagicMock(spec=httpx.Response, status_code=200),
        ]
    )

    c = AsyncClient(ssl_fallback_to_http=True)
    await c.open()
    resp = await c.request("get", "https://example.com")
    await c.close()

    calls = mock_instance.request.mock_calls
    # First call with https
    assert calls[0] == call("get", "https://example.com", headers=None, content=None)
    # Second call with http fallback
    assert calls[1] == call("get", "http://example.com", headers=None, content=None)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_request_ssl_error_no_fallback(async_mock_client):
    mock_instance = async_mock_client.return_value
    mock_instance.request = AsyncMock(side_effect=ssl.SSLError("SSL error"))

    c = AsyncClient(ssl_fallback_to_http=False)
    await c.open()
    with pytest.raises(ssl.SSLError):
        await c.request("get", "https://example.com")
    await c.close()


@pytest.mark.asyncio
async def test_get(async_mock_client):
    mock_instance = async_mock_client.return_value
    mock_instance.request = AsyncMock(
        return_value=MagicMock(spec=httpx.Response, status_code=200)
    )

    c = AsyncClient()
    await c.open()
    resp = await c.get("https://example.com")
    assert resp.status_code == 200
    await c.close()


@pytest.mark.asyncio
async def test_post(async_mock_client):
    mock_instance = async_mock_client.return_value
    mock_instance.request = AsyncMock(
        return_value=MagicMock(spec=httpx.Response, status_code=201)
    )

    c = AsyncClient()
    await c.open()
    resp = await c.post("https://example.com", content="some data")
    assert resp.status_code == 201
    await c.close()


@pytest.mark.asyncio
async def test_head(async_mock_client):
    mock_instance = async_mock_client.return_value
    mock_instance.request = AsyncMock(
        return_value=MagicMock(spec=httpx.Response, status_code=200)
    )

    c = AsyncClient()
    await c.open()
    resp = await c.head("https://example.com")
    assert resp.status_code == 200
    await c.close()


@pytest.mark.asyncio
async def test_stream(async_mock_client):
    """
    Test that the stream method yields a response, ensuring it's an async generator.
    """
    # This is the mock of `httpx.AsyncClient` (from your fixture)
    mock_instance = async_mock_client.return_value

    mock_stream_response = MagicMock(spec=httpx.Response)

    @asynccontextmanager
    async def mock_stream_context(*args, **kwargs):
        yield mock_stream_response

    # So now calling mock_instance.stream(...) returns our async context
    mock_instance.stream.side_effect = mock_stream_context

    c = AsyncClient()
    await c.open()

    collected = []
    # Because our `stream` is an async generator, we can do:
    async for r in c.stream("get", "https://example.com"):
        collected.append(r)

    assert collected == [mock_stream_response]

    await c.close()
