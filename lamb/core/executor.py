from __future__ import annotations
from collections.abc import Iterable
from typing import TYPE_CHECKING, Optional, Any, Type

import asyncio

from .backend import TaskWrapper, Executor

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Iterable, Mapping
    from selectors import BaseSelector

    from .bases import BaseMediator, BaseCommands, BaseSignals
    from .managers import HooksManager, RoutineContainer, RoutinesManager


class Signal:

    TERMINATE = 'TERMINATE'
    SKIP = 'SKIP'

    def __init__(self, name: str, args: Iterable[Any] = (),
                 kwargs: Optional[Mapping[str, Any]] = None):
        if kwargs is None:
            kwargs = {}
        self.name = name
        self.args = args
        self.kwargs = kwargs


class RoutineTaskWrapper(TaskWrapper):

    executor: RoutinesExecutor

    def __init__(self, executor: RoutinesExecutor, coro_func: Callable[..., Coroutine],
                 args: Iterable = (), kwargs: Optional[Mapping[str, Any]] = None, *,
                 priority: int, level: int, routine_container: RoutineContainer):
        super().__init__(executor, coro_func, args, kwargs, priority=priority)
        self.level = level
        self.routine_container = routine_container

    async def run(self):
        self.coro_func = self.routine_container.get_run_method()
        if not self.coro_func:
            return
        try:
            signal = await self.coro_func(*self.args, **self.kwargs)
            if signal:
                self.executor.process_signal(self.routine_container, signal)
        except BaseException as exc:
            self.exception = exc
            self.executor.append_exception(exc)
            self.backend.reset_loop()
            raise


class RoutinesExecutor(Executor):

    task_wrapper_cls: Type[RoutineTaskWrapper] = RoutineTaskWrapper

    tasks: dict[asyncio.Task, RoutineTaskWrapper]
    wrappers: list[RoutineTaskWrapper]
    containers: dict[RoutineContainer, RoutineTaskWrapper]
    exceptions: list[BaseException]

    def __init__(self, mediator: BaseMediator, commands: BaseCommands,
                 hooks_manager: HooksManager, routines_manager: RoutinesManager,
                 signals: BaseSignals, sentinel_selector: Optional[BaseSelector] = None,
                 correlation_key: Any = None, set_as_running: bool = False, start: bool = False):
        self.mediator = mediator
        self.commands = commands
        self.hooks_manager = hooks_manager
        self.routines_manager = routines_manager
        self.signals = signals
        self.containers = {}
        self.exceptions = []
        super().__init__(sentinel_selector=sentinel_selector, correlation_key=correlation_key,
                         set_as_running=set_as_running, start=start)

    def bootstrap(self, routines_manager: Optional[RoutinesManager] = None,
                  priority: int = 0, level: int = 0):
        if routines_manager is None:
            routines_manager = self.routines_manager
        for container in routines_manager.routines.values():
            routine = container.routine
            if routine.subroutines:
                priority = self.bootstrap(routine.subroutines_manager, priority=priority, level=level+1)
            coro_func = container.get_run_method()
            if coro_func:
                task_wrapper = self.task_wrapper_cls(
                    self, coro_func, priority=priority, level=level, routine_container=container)
                self.containers[container] = task_wrapper
                task_wrapper.schedule_task()
            priority += 1

        return priority

    def start(self, set_as_running: bool = False):
        if not self.running:
            super().start(set_as_running=set_as_running)
            self.bootstrap()

    def run_once(self, timeout: Optional[float] = 0):
        super().run_once(timeout=timeout)
        if self.exceptions:
            raise self.exceptions[0]

    def shutdown(self):
        super().shutdown()
        self.exceptions.clear()

    def append_exception(self, exc: BaseException):
        self.exceptions.append(exc)

    def cancel_siblings(self, container: RoutineContainer):
        level = self.containers[container].level
        found = False
        for cont, task_wrapper in self.containers.items():
            if found:
                task_wrapper.cancel_task()
                if task_wrapper.level < level:
                    break
            elif cont is container:
                found = True

    def process_signal(self, container: RoutineContainer, signal: Optional[Signal | str]):
        if isinstance(signal, Signal):
            signal_meth = getattr(self.signals, signal.name)
            signal = signal_meth(container, *signal.args, **signal.kwargs)
        if signal == Signal.TERMINATE:
            self.running = False
            self.cancel_tasks()
        elif signal == Signal.SKIP:
            self.cancel_siblings(container)
