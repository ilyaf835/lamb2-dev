from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional, Union

import atexit
import threading
import traceback
from heapq import heappush, heappop

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Collection, Callable


def thread_name_generator():
    c = 0
    while True:
        if c == 10000:
            c = 0
        c += 1
        yield f'Producer_thread_{c}'


gen_thread_name = thread_name_generator().__next__


class JThread(threading.Thread):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.join_on_exit = False


class LocksProxy:

    locks_dict: dict[str, threading.RLock]

    def __init__(self):
        self.locks_dict = {}

    def __getattr__(self, name: str):
        return self.get(name)

    def get(self, name: str):
        try:
            return self.locks_dict[name]
        except KeyError:
            lock = self.locks_dict[name] = threading.RLock()
            return lock

    def pop(self, name: str):
        return self.locks_dict.pop(name, None)


class SoftboundedSemaphore:

    def __init__(self, boundary: int = 0, limit_release: bool = False):
        self.boundary = max(boundary, 0)
        self.value = 0
        self.limit_release = limit_release
        self.cond = threading.Condition()

    def set_boundary(self, boundary: int):
        with self.cond:
            pb = self.boundary
            pv = self.value
            self.boundary = max(boundary, 0)
            self.value = min(self.value, self.boundary)
            if pv == pb < self.boundary:
                self.cond.notify()

    def acquire(self):
        with self.cond:
            while self.value == self.boundary:
                self.cond.wait()
            else:
                self.value += 1

    def release(self):
        with self.cond:
            if self.limit_release:
                if self.value > 0 or self.value == self.boundary == 0:
                    self.value -= 1
            else:
                self.value -= 1
            self.cond.notify()

    def reset(self):
        with self.cond:
            self.value = 0
            self.cond.notify_all()


class UnboundedSemaphore:

    def __init__(self, value: int = 0):
        self.value = max(value, 0)
        self.initial = self.value
        self.cond = threading.Condition()

    def acquire(self):
        with self.cond:
            while self.value == 0:
                self.cond.wait()
            else:
                self.value -= 1

    def release(self):
        with self.cond:
            self.value += 1
            self.cond.notify()

    def reset(self):
        with self.cond:
            self.value = self.initial
            self.cond.notify_all()


class DynamicBarrier:

    def __init__(self, boundary: int):
        self.boundary = max(boundary, 0)
        self.value = 0
        self.cond = threading.Condition()

    def set_boundary(self, boundary: int):
        with self.cond:
            self.boundary = max(boundary, 0)
            self.value = min(self.value, self.boundary)
            if self.value == self.boundary:
                self.cond.notify_all()

    def wait(self):
        with self.cond:
            while self.value < self.boundary:
                self.cond.wait()

    def notify(self):
        with self.cond:
            if self.value < self.boundary:
                self.value += 1
            if self.value == self.boundary:
                self.cond.notify_all()

    def notify_and_wait(self):
        with self.cond:
            self.notify()
            self.wait()

    def reset(self):
        with self.cond:
            self.value = 0
            self.cond.notify_all()


class LocksManager:

    locks: list[Union[threading.Lock, threading.RLock]]

    def __init__(self, locks: Optional[Iterable[Union[threading.Lock, threading.RLock]]] = None):
        self.locks = []
        if locks:
            self.locks.extend(locks)

    def acquire(self):
        for lock in self.locks:
            lock.acquire()

    def release(self):
        for lock in self.locks:
            lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class Waiter:

    succeeded: list[Task]
    canceled: list[Task]
    failed: list[Task]
    executing: list[Task]
    pending: list[Task]

    def __init__(self, tasks: Collection[Task], value: Optional[int] = None, ignore_exceptions: bool = True,
                 cancel_on_exception: bool = False, cancel_on_success: bool = False):
        self.tasks = tasks
        if value is None:
            self.value = len(tasks)
        else:
            self.value = min(len(tasks), max(value, 1))
        self.ignore_exceptions = ignore_exceptions
        self.cancel_on_exception = cancel_on_exception
        self.cancel_on_success = cancel_on_success

        self.running = False
        self.completed = False
        self.success = False

        self.succeeded = []
        self.canceled = []
        self.failed = []
        self.executing = []
        self.pending = []

        self.cancel_lock = threading.RLock()
        self.wait_semaphore = SoftboundedSemaphore(0)

    def cancel_pending(self):
        for task in self.pending.copy():
            task.cancel()

    def notify_executing(self, task: Task):
        if self.running:
            if task not in self.executing:
                self.executing.append(task)

    def notify_canceled(self, task: Task):
        if self.running:
            self.pending.remove(task)
            self.canceled.append(task)

    def notify_completed(self, task: Task):
        if self.running:
            if task in self.executing:
                self.executing.remove(task)
            self.pending.remove(task)
            if not task.exception:
                self.succeeded.append(task)
                self.value -= 1
            else:
                self.failed.append(task)
                if not self.ignore_exceptions:
                    if self.cancel_on_exception:
                        self.cancel_pending()
                    self.running = False
                    self.wait_semaphore.release()
                    return
            if not self.value:
                self.success = True
                if self.cancel_on_success:
                    self.cancel_pending()
                self.running = False
                self.wait_semaphore.release()
            elif not self.pending:
                self.running = False
                self.wait_semaphore.release()

    def wait(self):
        if not self.completed and self.tasks:
            if not self.running:
                self.running = True
                self.pending.extend(self.tasks)
                for task in self.tasks:
                    task.assign_waiter(self)
            self.wait_semaphore.acquire()
            self.completed = True

        return self.succeeded, self.failed, self.canceled, self.executing, self.pending


def wait(tasks: Collection[Task], n: Optional[int] = None, ignore_exceptions: bool = True,
         cancel_on_exception: bool = False, cancel_on_success: bool = False):
    return Waiter(tasks, n, ignore_exceptions=ignore_exceptions,
                  cancel_on_exception=cancel_on_exception,
                  cancel_on_success=cancel_on_success).wait()


class Task:

    waiters: list[Waiter]

    def __init__(self, func: Callable, args: Iterable[Any] = (), kwargs: Optional[Mapping[str, Any]] = None,
                priority: int = 0, join_on_exit: bool = False,
                success_callbacks: Optional[list[Callable]] = None,
                exception_callbacks: Optional[list[Callable]] = None,
                cancel_callbacks: Optional[list[Callable]] = None):
        self.func = func
        self.args = args
        if kwargs is None:
            kwargs = {}
        self.kwargs = kwargs
        self.priority = priority
        self.join_on_exit = join_on_exit
        if success_callbacks is None:
            success_callbacks = []
        if exception_callbacks is None:
            exception_callbacks = []
        if cancel_callbacks is None:
            cancel_callbacks = []
        self.success_callbacks = success_callbacks
        self.exception_callbacks = exception_callbacks
        self.cancel_callbacks = cancel_callbacks

        self.waiters = []
        self.waiters_lock = threading.RLock()
        self.cancel_locks = LocksManager()

        self.result = None
        self.exception = None

        self.running = False
        self.canceled = False
        self.completed = False

    def __lt__(self, other: Any):
        return self.priority < other.priority

    def assign_waiter(self, waiter: Waiter):
        with self.waiters_lock:
            self.cancel_locks.locks.append(waiter.cancel_lock)
            if self.completed:
                waiter.notify_completed(self)
            elif self.canceled:
                waiter.notify_canceled(self)
            else:
                if self.running:
                    waiter.notify_executing(self)
                self.waiters.append(waiter)

    def cancel(self):
        if self.running or self.completed:
            return
        self.canceled = True
        with self.waiters_lock:
            for waiter in self.waiters:
                waiter.notify_canceled(self)

    def execute(self):
        self.cancel_locks.acquire()
        if self.canceled:
            self.cancel_locks.release()
            for callback in self.cancel_callbacks:
                callback()
        elif not (self.running or self.completed):
            self.cancel_locks.release()
            with self.waiters_lock:
                for waiter in self.waiters:
                    waiter.notify_executing(self)
            self.running = True
            try:
                self.result = self.func(*self.args, **self.kwargs)
            except Exception as e:
                self.exception = e
                for callback in self.exception_callbacks:
                    callback(self.exception)
                raise
            else:
                for callback in self.success_callbacks:
                    callback(self.result)
            finally:
                self.completed = True
                self.running = False
                with self.waiters_lock, self.cancel_locks:
                    for waiter in self.waiters:
                        waiter.notify_completed(self)
                    self.waiters.clear()

        return self.result


class Producer:

    def __init__(self, queue: list[Task], queue_lock: threading.RLock,
                 threads: dict[str, JThread], threads_count: int):
        self.queue = queue
        self.queue_lock = queue_lock
        self.threads = threads
        self.threads_count = threads_count
        self.running = False

        self.threads_semaphore = SoftboundedSemaphore(self.threads_count, limit_release=True)
        self.queue_semaphore = UnboundedSemaphore(0)
        self.run_lock = threading.RLock()
        self.stop_lock = threading.RLock()

    def set_threads_count(self, count: int):
        self.threads_count = count
        self.threads_semaphore.set_boundary(count)

    def start(self, barrier: Optional[DynamicBarrier] = None):
        with self.stop_lock:
            if not self.running and self.threads_count > 0:
                JThread(target=self.run, args=(barrier,), daemon=True).start()

    def stop(self):
        if self.running:
            with self.stop_lock:
                self.running = False
                self.queue_semaphore.release()
                self.threads_semaphore.release()

    def notify(self):
        if self.running:
            self.queue_semaphore.release()

    def run(self, barrier: Optional[DynamicBarrier] = None):
        with self.run_lock:
            self.queue_semaphore.reset()
            self.running = True
            if barrier:
                barrier.notify_and_wait()
                del barrier
            while True:
                self.threads_semaphore.acquire()
                if not self.running:
                    break
                self.queue_semaphore.acquire()
                if not self.running:
                    break
                with self.stop_lock:
                    if not self.running:
                        break
                    self.queue_lock.acquire()
                    if self.queue:
                        task = heappop(self.queue)
                        self.queue_lock.release()
                        self.spawn_thread(task)
                    else:
                        self.queue_lock.release()
                        self.threads_semaphore.release()

    def gen_thread_name(self):
        name = gen_thread_name()
        while name in self.threads:
            name = gen_thread_name()

        return name

    def spawn_thread(self, task: Task):
        name = self.gen_thread_name()
        thread = self.threads[name] = JThread(
            target=self.drain_queue, name=name, args=(name, task), daemon=True)
        thread.join_on_exit = task.join_on_exit
        thread.start()

    def spawn_forced(self, task: Task):
        name = self.gen_thread_name()
        thread = self.threads[name] = JThread(
            target=self.execute_forced, name=name, args=(name, task), daemon=True)
        thread.join_on_exit = task.join_on_exit
        thread.start()

    def drain_queue(self, thread_name, task):
        thread = self.threads[thread_name]
        self.execute(thread, task)
        while self.running:
            with self.queue_lock:
                if self.queue:
                    task = heappop(self.queue)
                else:
                    break
            self.execute(thread, task)
        self.threads.pop(thread_name)
        self.threads_semaphore.release()

    def execute_forced(self, thread_name: str, task: Task):
        self.execute(self.threads[thread_name], task)
        self.threads.pop(thread_name)

    def execute(self, thread: JThread, task: Task):
        thread.join_on_exit = task.join_on_exit
        try:
            task.execute()
        except Exception as e:
            traceback.print_exception(e.__class__, e, e.__traceback__)
        finally:
            thread.join_on_exit = False


class Worker:

    def __init__(self, queue: list[Task], queue_lock: threading.RLock, threads: dict[Worker, JThread]):
        self.queue = queue
        self.queue_lock = queue_lock
        self.threads = threads
        self.completed = True
        self.running = False

        self.queue_semaphore = SoftboundedSemaphore(0)
        self.run_lock = threading.RLock()
        self.stop_lock = threading.RLock()

    def start(self, barrier: Optional[DynamicBarrier] = None):
        with self.stop_lock:
            if self.completed:
                thread = self.threads[self] = JThread(target=self.run, args=(barrier,), daemon=True)
                thread.start()
            else:
                self.running = True
                if barrier:
                    barrier.notify()

    def stop(self):
        if self.running:
            with self.stop_lock:
                self.running = False
                self.queue_semaphore.release()

    def notify(self):
        if self.running:
            self.queue_semaphore.release()

    def run(self, barrier: Optional[DynamicBarrier] = None):
        with self.run_lock:
            self.queue_semaphore.reset()
            self.completed = False
            self.running = True
            thread = self.threads[self]
            if barrier:
                barrier.notify_and_wait()
                del barrier
            while self.running:
                self.queue_lock.acquire()
                if self.queue:
                    task = heappop(self.queue)
                    self.queue_lock.release()
                    self.execute(thread, task)
                else:
                    self.queue_lock.release()
                    self.queue_semaphore.acquire()
            self.completed = True
            self.threads.pop(self)

    def execute(self, thread: JThread, task: Task):
        thread.join_on_exit = task.join_on_exit
        try:
            task.execute()
        except Exception as e:
            traceback.print_exception(e.__class__, e, e.__traceback__)
        finally:
            thread.join_on_exit = False


class ThreadsHandler:

    workers_threads: dict[Worker, JThread]
    producer_threads: dict[str, JThread]
    queue: list[Task]

    def __init__(self, workers_count: int = 4, additional_threads: int = 0, start: bool = True):
        self.workers_count = max(workers_count, 0)
        self.additional_threads = max(additional_threads, 0)
        self.running = False

        self.workers_threads = {}
        self.producer_threads = {}
        self.queue = []
        self.queue_lock = threading.RLock()

        self.workers = [Worker(self.queue, self.queue_lock, self.workers_threads)
                        for i in range(self.workers_count)]
        self.producer = Producer(
            self.queue, self.queue_lock, self.producer_threads, self.additional_threads)

        atexit.register(self.atexit)
        if start:
            self.start()

    def atexit(self):
        self.stop()
        for thread in self.workers_threads.copy().values():
            if thread.join_on_exit:
                thread.join()
        for thread in self.producer_threads.copy().values():
            if thread.join_on_exit:
                thread.join()

    def join(self):
        self.stop()
        for thread in self.workers_threads.copy().values():
            thread.join()
        for thread in self.producer_threads.copy().values():
            thread.join()

    def add_worker(self):
        worker = Worker(self.queue, self.queue_lock, self.workers_threads)
        self.workers_count += 1
        self.workers.append(worker)
        if self.running:
            worker.start()

    def remove_worker(self):
        if self.workers:
            self.workers_count -= 1
            self.workers.pop().stop()

    def set_producer_threads(self, thread_count: int):
        self.additional_threads = max(thread_count, 0)
        self.producer.set_threads_count(self.additional_threads)

    def clear_queue(self):
        with self.queue_lock:
            self.queue.clear()

    def start(self):
        if not self.running:
            self.running = True
            barrier = DynamicBarrier(self.workers_count + min(self.additional_threads, 1))
            for worker in self.workers:
                worker.start(barrier)
            self.producer.start(barrier)
            barrier.wait()
            with self.queue_lock:
                if self.queue:
                    for worker in self.workers:
                        worker.notify()
                    for task in self.queue:
                        self.producer.notify()

    def stop(self):
        if self.running:
            self.running = False
            for worker in self.workers:
                worker.stop()
            self.producer.stop()

    def notify(self):
        with self.queue_lock:
            for worker in self.workers:
                worker.notify()
            for task in self.queue:
                self.producer.notify()

    def enqueue(self, func: Callable, args: Iterable = (), kwargs: Optional[Mapping[str, Any]] = None,
                priority: int = 0, join_on_exit: bool = False, force: bool = False,
                success_callbacks: Optional[list[Callable]] = None,
                exception_callbacks: Optional[list[Callable]] = None,
                cancel_callbacks: Optional[list[Callable]] = None):
        if kwargs is None:
            kwargs = {}
        task = Task(func, args, kwargs, priority=priority,  join_on_exit=join_on_exit,
                    success_callbacks=success_callbacks, exception_callbacks=exception_callbacks,
                    cancel_callbacks=cancel_callbacks)
        if force:
            self.producer.spawn_forced(task)
        else:
            with self.queue_lock:
                heappush(self.queue, task)
            if self.running:
                self.notify()

        return task
