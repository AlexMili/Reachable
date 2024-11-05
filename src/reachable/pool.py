import asyncio
from types import TracebackType
from typing import Any, Awaitable, List, Optional, Type

from tqdm.asyncio import tqdm


# Based on
# https://medium.com/@cgarciae/making-an-infinite-number-of-requests-with-python-aiohttp-pypeln-3a552b97dc95
class TaskPool(object):
    def __init__(self, workers: int, use_tqdm: bool = True):
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(workers)
        self._tasks: List[Awaitable[Any]] = []
        self._results: List[Any] = []
        self.use_tqdm: bool = use_tqdm

    async def put(self, coro: Awaitable[Any]) -> None:
        await self._semaphore.acquire()

        task: Any = asyncio.ensure_future(coro)
        task.add_done_callback(self._on_task_done)
        self._tasks.append(task)

    def _on_task_done(self, task: Any) -> None:
        try:
            res = task.result()
            self._results.append(res)
        except Exception as e:
            print(f"Task raised an exception: {e}")
        finally:
            self._semaphore.release()

    async def join(self) -> None:
        if self.use_tqdm:
            await tqdm.gather(*self._tasks)
        else:
            await asyncio.gather(*self._tasks)

    async def __aenter__(self) -> Any:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        await self.join()
