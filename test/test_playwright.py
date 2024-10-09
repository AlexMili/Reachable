import asyncio

from tqdm.asyncio import tqdm

from reachable import is_reachable_async
from reachable.client import AsyncPlaywrightClient
from reachable.pool import TaskPool


# Please provide your Chromium path here
chromium_path: str = ""


def test_async():
    urls = ["https://google.com", "https://bing.com"]

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop already exists so we crete one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def wrapper():
        async with AsyncPlaywrightClient(
            headless=True,
            executable_path=chromium_path,
        ) as client:
            tasks = [client.request(url) for url in urls]
            return await tqdm.gather(*tasks)

    try:
        result = loop.run_until_complete(wrapper())
    finally:
        loop.close()

    assert len(result) == len(urls)


async def _executor(url, client):
    result = await is_reachable_async(
        url,
        client=client,
        include_response=True,
    )
    return result


async def _wrapper(urls):
    async with AsyncPlaywrightClient(
        headless=True,
        executable_path=chromium_path,
        ensure_protocol_url=True,
        ssl_fallback_to_http=True,
    ) as client:
        tasks = TaskPool(workers=10)

        for url in tqdm(urls, desc="Loading data"):
            await tasks.put(_executor(url, client))

        await tasks.join()

    return tasks._results


def test_pool():
    urls = ["https://google.com", "https://bing.com"]

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop already exists so we crete one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    results = loop.run_until_complete(_wrapper(urls))

    assert len(results) == len(urls)
