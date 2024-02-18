from __future__ import annotations

import time

from bot.mods.chat.exceptions import ChatApiError
from bot.routines import ChatRoutine as DefaultChatRoutine
from bot.routines.subroutines.base import BaseSubroutine
from bot.routines.subroutines import (
    ExceptionsSentinelSubroutine,
    MessagesProcessingSubroutine,
    CommandsProcessingSubroutine
)
from bot.commands import CommandsT
from .mediator import MediatorT


class MessagesUpdatingSubroutine(BaseSubroutine[MediatorT, CommandsT]):

    max_retries = 2

    async def get_room_update(self):
        retries = self.max_retries
        while True:
            try:
                return await self.mediator.room.async_get_update()
            except ChatApiError:
                if not retries:
                    raise
                retries -= 1

    async def run(self, *args, **kwargs):
        room_json = await self.get_room_update()
        with self.mediator.locks.chat:
            messages = self.mediator.room.update_room(room_json)
        self.messages_queue.extend(messages)


class MusicPlayerRoutine(BaseSubroutine[MediatorT, CommandsT]):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.locks = self.mediator.locks
        self.player = self.mediator.player
        self.room = self.mediator.room

    def is_playing(self):
        if self.player.current_track:
            return time.monotonic() < self.player.timestamp + self.player.current_track.duration
        return False

    def pop_track(self):
        if self.player.repeat:
            return self.player.current_track or self.player.pop_track()
        else:
            return self.player.pop_track()

    async def run(self):
        if not self.mediator.is_player_available():
            return
        with self.locks.player:
            if self.player.paused or self.is_playing():
                return
            if not self.player.queue:
                self.player.current_track = None
            else:
                track = self.player.current_track = self.pop_track()
                await self.room.async_launch_player(track.title, track.stream_url)
                self.player.set_timestamp()


class ChatRoutine(DefaultChatRoutine[MediatorT, CommandsT]):

    subroutines = [
        ExceptionsSentinelSubroutine,
        MessagesUpdatingSubroutine,
        MessagesProcessingSubroutine,
        CommandsProcessingSubroutine,
        MusicPlayerRoutine]
