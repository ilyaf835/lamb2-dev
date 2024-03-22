from __future__ import annotations
from typing import TYPE_CHECKING, Type, TypeVar, Generic, Any, Optional

import sys
import asyncio
import threading
from bisect import bisect
from selectors import BaseSelector

if TYPE_CHECKING:
    from _typeshed import FileDescriptorLike
    from selectors import _EventMask

    from collections.abc import Callable, Coroutine, Iterable, Mapping
    from collections import deque


ExecutorT = TypeVar('ExecutorT', bound='Executor')


def noop():
    return


class SelectorDemuxer(BaseSelector):

    sentinel_selector: BaseSelector
    target_selector: BaseSelector

    def __init__(self, *, sentinel_selector: BaseSelector,
                 target_selector: BaseSelector, correlation_key: Any):
        if sentinel_selector is target_selector:
            raise ValueError('Must be different selectors')
        self.__dict__['sentinel_selector'] = sentinel_selector
        self.__dict__['target_selector'] = target_selector
        self.__dict__['correlation_key'] = correlation_key

    def register(self, fileobj: FileDescriptorLike, events: _EventMask, data: Any = None):
        self.sentinel_selector.register(fileobj, events, (self.correlation_key, data))
        return self.target_selector.register(fileobj, events, data)

    def unregister(self, fileobj: FileDescriptorLike):
        self.sentinel_selector.unregister(fileobj)
        return self.target_selector.unregister(fileobj)

    def modify(self, fileobj: FileDescriptorLike, events: _EventMask, data: Any = None):
        self.sentinel_selector.unregister(fileobj)
        self.sentinel_selector.register(fileobj, events, (self.correlation_key, data))
        self.target_selector.unregister(fileobj)
        return self.target_selector.register(fileobj, events, data)

    def select(self, timeout: Optional[float] = None):
        return self.target_selector.select(timeout)

    def get_map(self):
        return self.target_selector.get_map()

    def get_key(self, fileobj: FileDescriptorLike):
        return self.target_selector.get_key(fileobj)

    def close(self):
        for key in self.target_selector._fd_to_key.values():                          # type: ignore
            self.sentinel_selector.unregister(key.fileobj)
        self.target_selector.close()

    def __enter__(self):
        return self.target_selector

    def __exit__(self, *args):
        self.close()

    def __getattr__(self, key: str):
        return getattr(self.target_selector, key)

    def __setattr__(self, key: str, value: Any):
        setattr(self.target_selector, key, value)


class AsyncioBackend:

    ready: deque[asyncio.Handle | asyncio.TimerHandle]

    def __init__(self, sentinel_selector: Optional[BaseSelector] = None,
                 correlation_key: Any = None):
        self.loop = asyncio.new_event_loop()
        self.loop._set_coroutine_origin_tracking(self.loop._debug)                    # type: ignore
        self.ready = self.loop._ready                                                 # type: ignore
        if sentinel_selector:
            self.loop._selector = SelectorDemuxer(                                    # type: ignore
                sentinel_selector=sentinel_selector,
                target_selector=self.loop._selector,                                  # type: ignore
                correlation_key=correlation_key)

    def create_task(self, coro: Coroutine):
        return self.loop.create_task(coro)

    def run_once(self, timeout: Optional[float] = 0):
        self.loop._check_closed()                                                     # type: ignore
        if self.loop is not asyncio.events._get_running_loop():
            asyncio.events._set_running_loop(self.loop)
            asyncio.set_event_loop(self.loop)
            sys.set_asyncgen_hooks(
                firstiter=self.loop._asyncgen_firstiter_hook,                         # type: ignore
                finalizer=self.loop._asyncgen_finalizer_hook)                         # type: ignore
            self.loop._thread_id = threading.get_ident()                              # type: ignore
        if not self.loop._ready and timeout is not None:                              # type: ignore
            timeout = max(timeout, 0)
            if not self.loop._scheduled or (                                          # type: ignore
                self.loop._scheduled[0]._when - self.loop.time() > timeout):          # type: ignore
                self.loop.call_later(timeout, noop)
        self.loop._run_once()                                                         # type: ignore

    def reset_loop(self, keep_callbacks=False):
        tasks = set(asyncio.all_tasks())
        for task in tasks:
            task._log_destroy_pending = False                                         # type: ignore
            task.cancel()
            asyncio.tasks._unregister_task(task)
        for handle in self.loop._ready:                                               # type: ignore
            if keep_callbacks:
                callback = handle._callback                                           # type: ignore
                if (hasattr(callback, '__self__') and callback.__self__ in tasks):
                    continue
            handle.cancel()
        for handle in self.loop._scheduled:                                           # type: ignore
            handle.cancel()

    def shutdown(self):
        sys.set_asyncgen_hooks(
            firstiter=self.loop._asyncgen_firstiter_hook,                             # type: ignore
            finalizer=self.loop._asyncgen_finalizer_hook)                             # type: ignore
        self.loop._stopping = False                                                   # type: ignore
        self.loop._thread_id = None                                                   # type: ignore
        asyncio.events._set_running_loop(None)
        self.loop._set_coroutine_origin_tracking(False)                               # type: ignore
        try:
            asyncio.runners._cancel_all_tasks(self.loop)                              # type: ignore
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
        finally:
            asyncio.events.set_event_loop(None)
            self.loop.close()


class TaskWrapper(Generic[ExecutorT]):

    def __init__(self, executor: ExecutorT, coro_func: Callable[..., Coroutine],
                 args: Iterable, kwargs: Optional[Mapping[str, Any]], priority: int):
        if kwargs is None:
            kwargs = {}
        self.executor = executor
        self.backend = executor.backend
        self.coro_func = coro_func
        self.args = args
        self.kwargs = kwargs
        self.priority = priority
        self.index = -1
        self.exception = None

    def __lt__(self, other: Any):
        return self.priority < other.priority

    def schedule_task(self):
        self.task = self.backend.create_task(self.run())
        self.executor.tasks[self.task] = self
        wrappers_len = len(self.executor.wrappers)
        pos = bisect(self.executor.wrappers, self)
        if pos >= wrappers_len:
            self.executor.wrappers.append(self)
            self.index = len(self.backend.ready) - 1
        else:
            next_wrapper = self.executor.wrappers[pos]
            handle = self.backend.ready.pop()
            self.index = next_wrapper.index
            next_wrapper.index += 1
            self.executor.wrappers.insert(pos, self)
            self.backend.ready.insert(self.index, handle)

    def cancel_task(self):
        self.task.cancel()

    async def run(self):
        try:
            return await self.coro_func(*self.args, **self.kwargs)
        except BaseException as exc:
            self.exception = exc
            raise


class Executor:

    backend_cls: Type[AsyncioBackend] = AsyncioBackend
    task_wrapper_cls: Type[TaskWrapper] = TaskWrapper

    tasks: dict[asyncio.Task, TaskWrapper]
    wrappers: list[TaskWrapper]

    def __init__(self, sentinel_selector: Optional[BaseSelector] = None,
                 correlation_key: Any = None, start=True):
        self.tasks = {}
        self.wrappers = []
        self.running = False
        self.sentinel_selector = sentinel_selector
        if not correlation_key:
            correlation_key = id(self)
        self.correlation_key = correlation_key
        if start:
            self.start()

    def start(self):
        if not self.running:
            self.backend = self.backend_cls(
                sentinel_selector=self.sentinel_selector,
                correlation_key=self.correlation_key)
            self.running = True

    def run_once(self, timeout: Optional[float] = 0):
        if self.running:
            self.backend.run_once(timeout=timeout)
            self.reschedule_tasks()

    def shutdown(self):
        if self.running:
            self.running = False
            self.tasks.clear()
            self.wrappers.clear()
            self.backend.shutdown()

    def cancel_tasks(self):
        for task_wrapper in self.wrappers:
            task_wrapper.cancel_task()

    def create_task(self, coro_func: Callable[..., Coroutine], *, args: Iterable = (),
                    kwargs: Optional[Mapping[str, Any]] = None, priority: int = 0):
        return self.task_wrapper_cls(self, coro_func, args, kwargs, priority)

    def reschedule_tasks(self):
        finished_tasks = [
            self.tasks.pop(task_wrapper.task)
            for task_wrapper in self.wrappers if task_wrapper.task.done()]
        if not finished_tasks:
            return
        wrappers_len = len(self.wrappers)
        index = len(self.backend.ready)
        self.update_indices()
        for task_wrapper in finished_tasks:
            task = self.backend.create_task(task_wrapper.run())
            task_wrapper.task = task
            self.tasks[task] = task_wrapper
            pos = bisect(self.wrappers, task_wrapper)
            if pos >= wrappers_len:
                task_wrapper.index = index
            else:
                next_wrapper = self.wrappers[pos]
                task_wrapper.index = next_wrapper.index
                next_wrapper.index += 1
                handle = self.backend.ready.pop()
                self.backend.ready.insert(task_wrapper.index, handle)
            index += 1

    def update_indices(self):
        count = len(self.tasks)
        for index, handle in enumerate(self.backend.ready):
            callback = handle._callback                                 # type: ignore
            if not hasattr(callback, '__self__'):
                continue
            task_wrapper = self.tasks.get(callback.__self__)
            if not task_wrapper:
                continue
            task_wrapper.index = index
            count -= 1
            if not count:
                break
