from __future__ import annotations

from bot.mods.chat.exceptions import ChatApiError
from bot.routines import ChatRoutine as DefaultChatRoutine
from bot.routines.subroutines.base import BaseSubroutine
from bot.routines.subroutines import (
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


class ChatRoutine(DefaultChatRoutine[MediatorT, CommandsT]):

    subroutines = [
        MessagesUpdatingSubroutine,
        MessagesProcessingSubroutine,
        CommandsProcessingSubroutine]
