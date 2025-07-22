import pytest

from reachable import is_reachable, is_reachable_async
from reachable.client import AsyncClient, AsyncPlaywrightClient, Client


chromium_path: str = ""


@pytest.mark.skip(reason="Need to start a local proxy")
@pytest.mark.asyncio
async def test_proxy_playwright():
    async with AsyncPlaywrightClient(
        headless=True,
        executable_path=chromium_path,
        proxy_url="http://localhost:8080",
    ) as client:
        result = await is_reachable_async("http://google.com", client=client)
    assert isinstance(result, dict)
    assert result["success"] is True


@pytest.mark.skip(reason="Need to start a local proxy")
@pytest.mark.asyncio
async def test_proxy_async():
    async with AsyncClient(proxy_url="http://localhost:8080") as client:
        result = await is_reachable_async("http://google.com", client=client)
    assert isinstance(result, dict)
    assert result["success"] is True


@pytest.mark.skip(reason="Need to start a local proxy")
@pytest.mark.asyncio
def test_proxy_sync():
    client = Client(proxy_url="http://localhost:8080")
    result = is_reachable("http://google.com", client=client)
    assert isinstance(result, dict)
    assert result["success"] is True
