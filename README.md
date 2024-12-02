**Reachable** checks if a URL exists and is reachable.

# Features
- Use `HEAD`request instead of `GET` to save some bandwidth
- Follow redirects
- Handle local redirects (without full URL in `location` header)
- Record all the URLs of the redirection chain
- Check if redirected URL match the TLD of source URL
- Detect Cloudflare protection
- Avoid basic bot detectors
    - Use randome Chrome user agent
    - Wait between consecutive requests to the same host
    - Include `Host` header
- Use of HTTP/2
- Detect parking domains

# Installation
You can install it with pip :
```bash
pip install reachable
```
Or clone this repository and simply run :
```bash
cd reachable/
pip install -e .
```

# Usage

## Simple URL
```python
from reachable import is_reachable
result = is_reachable("https://google.com")
```

The output will look like this:
```json
{
    "original_url": "https://google.com",
    "final_url": "https://www.google.com/",
    "response": null, 
    "status_code": 200,
    "success": true,
    "error_name": null,
    "cloudflare_protection": false,
    "redirect": {
        "chain": ["https://www.google.com/"],
        "final_url": "https://www.google.com/",
        "tld_match": true
    }
}
```

## Multiple URLs
```python
from reachable import is_reachable
result = is_reachable(["https://google.com", "http://bing.com"])
```

The output will look like this:
```json
[
    {
        "original_url": "https://google.com",
        "final_url": "https://www.google.com/",
        "response": null, 
        "status_code": 200,
        "success": true,
        "error_name": null,
        "cloudflare_protection": false,
        "redirect": {
            "chain": ["https://www.google.com/"],
            "final_url": "https://www.google.com/",
            "tld_match": true
        }
    },
    {
        "original_url": "http://bing.com",
        "final_url": "https://www.bing.com/?toWww=1&redig=16A78C94",
        "response": null,
        "status_code": 200,
        "success": true,
        "error_name": null,
        "cloudflare_protection": false,
        "redirect": {
            "chain": ["https://www.bing.com:443/?toWww=1&redig=16A78C94"],
            "final_url": "https://www.bing.com/?toWww=1&redig=16A78C94",
            "tld_match": true
        }
    }
]
```

## Async
```python
import asyncio
from reachable import is_reachable_async

result = asyncio.run(is_reachable_async("https://google.com"))
```
or
```python
import asyncio
from reachable import is_reachable_async

urls = ["https://google.com", "https://bing.com"]

try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    # No loop already exists so we crete one
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
try:
    result = loop.run_until_complete(asyncio.gather(*[is_reachable_async(url) for url in urls]))
finally:
    loop.close()
```

### Handling high volumes with Taskpool

If you want to process a large number of URLs (> 500) you will quickly hit the limits of your hardware and/or OS because you can only open a defined number of active connections.

To bypass this problem you can use the `TaskPool` class. It uses Asyncio Semaphores to limit the number of asyncio threads running. It works by acquiring a lock when starting the worker and releasing it when done. It allows to always have a number of asyncio workers without overwhelming the OS.

```python
import asyncio

from reachable import is_reachable_async
from reachable.client import AsyncClient
from reachable.pool import TaskPool


urls = ["https://google.com", "https://bing.com"]


async def worker(url, client):
    result = await is_reachable_async(url, client=client)
    return result


async def workers_builder(urls, pool_size: int = 100):
    async with AsyncClient() as client:
        tasks = TaskPool(workers=pool_size)

        for url in urls:
            await tasks.put(worker(url, client=client))

        await tasks.join()

    return tasks._results


try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    # No loop already exists so we crete one
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

try:
    result = loop.run_until_complete(workers_builder(urls))
    print(result)
finally:
    loop.close()

```