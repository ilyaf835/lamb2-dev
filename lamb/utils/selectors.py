from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional

from selectors import BaseSelector

if TYPE_CHECKING:
    from _typeshed import FileDescriptorLike
    from selectors import _EventMask


class SelectorDemuxer(BaseSelector):

    sentinel_selector: BaseSelector
    target_selector: BaseSelector

    def __init__(self, sentinel_selector: BaseSelector,
                 target_selector: BaseSelector, correlation_key: Any):
        self.__dict__['sentinel_selector'] = sentinel_selector
        self.__dict__['target_selector'] = target_selector
        self.__dict__['correlation_key'] = correlation_key
        for key in self.target_selector._fd_to_key.values():                          # type: ignore
            self.sentinel_selector.register(
                key.fileobj, key.events, (self.correlation_key, key.data))

    def register(self, fileobj: FileDescriptorLike,
                 events: _EventMask, data: Any = None):
        self.sentinel_selector.register(
            fileobj, events, (self.correlation_key, data))
        return self.target_selector.register(fileobj, events, data)

    def unregister(self, fileobj: FileDescriptorLike):
        if fileobj in self.sentinel_selector._map:                                    # type: ignore
            self.sentinel_selector.unregister(fileobj)
        return self.target_selector.unregister(fileobj)

    def modify(self, fileobj: FileDescriptorLike,
               events: _EventMask, data: Any = None):
        if fileobj in self.sentinel_selector._map:                                    # type: ignore
            self.sentinel_selector.unregister(fileobj)
        self.sentinel_selector.register(
            fileobj, events, (self.correlation_key, data))
        self.target_selector.unregister(fileobj)
        return self.target_selector.register(fileobj, events, data)

    def select(self, timeout: Optional[float] = None):
        return self.target_selector.select(timeout)

    def get_map(self):
        return self.target_selector.get_map()

    def get_key(self, fileobj: FileDescriptorLike):
        return self.target_selector.get_key(fileobj)

    def close(self):
        for fd, key in self.target_selector._fd_to_key.items():                       # type: ignore
            if fd in self.sentinel_selector._fd_to_key:                               # type: ignore
                self.sentinel_selector.unregister(key.fileobj)
        self.target_selector.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __getattr__(self, key: str):
        return getattr(self.target_selector, key)

    def __setattr__(self, key: str, value: Any):
        setattr(self.target_selector, key, value)
