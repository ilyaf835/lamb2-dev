from __future__ import annotations
from typing import Optional

import time
from attrs import define

from .exceptions import (
    TrackDurationError,
    QueueLimitError,
    EmptyQueueError,
    QueueIndexError
)


@define
class Track:
    title: str
    duration: int
    origin_id: str
    origin_url: str
    stream_url: str


class Player:

    current_track: Optional[Track]
    queue: list[Track]

    def __init__(self, duration_limit: float = float('inf'), queue_limit: float = float('inf')):
        self.duration_limit = duration_limit
        self.queue_limit = queue_limit
        self.queue = []
        self.timestamp = 0.0
        self.current_track = None
        self.repeat = False
        self.paused = False

    def set_queue_limit(self, limit: int):
        self.queue_limit = limit

    def set_duration_limit(self, limit: int):
        self.duration_limit = limit

    def set_timestamp(self):
        self.timestamp = time.monotonic()

    def reset_timestamp(self):
        self.timestamp = 0

    def clear_queue(self):
        self.queue.clear()

    def pause(self):
        self.paused = True

    def unpause(self):
        self.paused = False

    def add_track(self, track: Track, index: Optional[int] = None,
                  extend_queue: bool = False, extend_duration: bool = False):
        if track.duration > self.duration_limit and not extend_duration:
            raise TrackDurationError(format_args=(self.duration_limit,))
        if len(self.queue) >= self.queue_limit and not extend_queue:
            raise QueueLimitError(format_args=(self.queue_limit,))

        if index is None:
            self.queue.append(track)
        else:
            self.queue.insert(index, track)

    def pop_track(self, index: int = 0):
        if not self.queue:
            raise EmptyQueueError()
        try:
            return self.queue.pop(index)
        except IndexError:
            raise QueueIndexError()
