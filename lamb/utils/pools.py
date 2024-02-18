from typing import Type

import types
import threading
from collections import deque


class PoolWrapper:

    def __init__(self, queue: deque, semaphore: threading.Semaphore):
        self.queue = queue
        self.semaphore = semaphore
        self.item = None

    def append_conn(self):
        self.queue.append(self.item)
        self.item = None
        self.semaphore.release()

    def pop_conn(self):
        self.semaphore.acquire()
        self.item = self.queue.popleft()

        return self.item

    def __enter__(self):
        return self.pop_conn()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.append_conn()


class BasePool:

    wrapper_cls: Type[PoolWrapper] = PoolWrapper

    def __init__(self, count: int):
        self.count = max(count, 1)
        self.queue = deque()
        self.semaphore = threading.Semaphore(count)

    def get_item(self):
        return self.wrapper_cls(self.queue, self.semaphore)


@types.coroutine
def switch():
    yield


class AsyncPoolWrapper:

    def __init__(self, queue: deque):
        self.queue = queue
        self.item = None

    def append_conn(self):
        self.queue.append(self.item)
        self.item = None

    async def pop_conn(self):
        queue = self.queue
        while not queue:
            await switch()
        self.item = queue.popleft()
        return self.item

    async def __aenter__(self):
        return await self.pop_conn()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.append_conn()


class AsyncBasePool:

    wrapper_cls: Type[AsyncPoolWrapper] = AsyncPoolWrapper

    def __init__(self, count: int):
        self.count = max(count, 1)
        self.queue = deque()

    def get_item(self):
        return self.wrapper_cls(self.queue)
