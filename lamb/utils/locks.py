from __future__ import annotations

import asyncio
import threading
from weakref import WeakValueDictionary


class AsyncLocksProxy:

    weakvaluedict: WeakValueDictionary[str, asyncio.Lock]

    def __init__(self):
        self.weakvaluedict = WeakValueDictionary()
        self.lock = threading.RLock()

    def get(self, key: str):
        with self.lock:
            lock = self.weakvaluedict.get(key)
            if not lock:
                lock = self.weakvaluedict[key] = asyncio.Lock()

            return lock


class AsyncEventProxy:

    weakvaluedict: WeakValueDictionary[asyncio.AbstractEventLoop, asyncio.Event]

    def __init__(self):
        self.weakvaluedict = WeakValueDictionary()
        self.lock = threading.RLock()

    def get(self):
        with self.lock:
            event_loop = asyncio.get_running_loop()
            event = self.weakvaluedict.get(event_loop)
            if not event:
                event = self.weakvaluedict[event_loop] = asyncio.Event()

            return event
