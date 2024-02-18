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
