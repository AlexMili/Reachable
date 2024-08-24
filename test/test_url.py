import asyncio

from tqdm.asyncio import tqdm

from reachable import is_reachable, is_reachable_async
from reachable.client import AsyncClient


def test_serp():
    result = is_reachable("https://google.com")
    result2 = is_reachable(["https://google.com", "https://bing.com"])
    assert isinstance(result, dict)
    assert len(result2) == 2


def test_async():
    urls = ["https://google.com", "https://bing.com"]

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop already exists so we crete one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            asyncio.gather(*[is_reachable_async(url) for url in urls])
        )
    finally:
        loop.close()

    assert len(result) == 2


def test_async2():
    urls = ["https://google.com", "https://bing.com"]

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop already exists so we crete one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def wrapper():
        async with AsyncClient(include_host=True) as client:
            tasks = [is_reachable_async(url, client=client) for url in urls]
            return await tqdm.gather(*tasks)

    try:
        result = loop.run_until_complete(wrapper())
    finally:
        loop.close()

    assert len(result) == 2
