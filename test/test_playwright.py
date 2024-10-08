import asyncio

from tqdm.asyncio import tqdm

from reachable.client import AsyncPlaywrightClient


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
            executable_path="/Applications/Chromium.app/Contents/MacOS/Chromium",
        ) as client:
            tasks = [client.request(url) for url in urls]
            return await tqdm.gather(*tasks)

    try:
        result = loop.run_until_complete(wrapper())
    finally:
        loop.close()

    assert len(result) == len(urls)
