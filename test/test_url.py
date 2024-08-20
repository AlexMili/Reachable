import asyncio

from reachable import is_reachable, is_reachable_async


def test_serp():
    result = is_reachable("https://google.com")
    result2 = is_reachable(["https://google.com", "https://bing.com"])
    print("Done")


def test_async():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop already exists so we crete one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(is_reachable_async(["https://google.com", "https://bing.com"]))
    finally:
        loop.close()
