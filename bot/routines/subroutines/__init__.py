from bot.mods.chat.exceptions import ChatApiError

from .base import BaseSubroutine
from .commands import CommandsSpamSubroutine, ExecuteCommandSubroutine
from .messages import (
    SkipBotMessageSubroutine,
    MessageHooksTriggerSubroutine,
    MusicMessageSubroutine,
    MessageParsingSubroutine
)

from bot.mediator import MediatorT
from bot.commands import CommandsT


class MessagesUpdatingSubroutine(BaseSubroutine[MediatorT, CommandsT]):

    MAX_RETRIES = 2

    def get_room_update(self):
        retries = self.MAX_RETRIES
        while True:
            try:
                return self.mediator.room.get_update()
            except ChatApiError:
                if not retries:
                    raise
                retries -= 1

    async def run(self, *args, **kwargs):
        room_json = self.get_room_update()
        with self.mediator.locks.chat:
            messages = self.mediator.room.update_room(room_json)
        self.messages_queue.extend(messages)


class MessagesProcessingSubroutine(BaseSubroutine[MediatorT, CommandsT]):

    local_subroutines = [
        SkipBotMessageSubroutine,
        MessageHooksTriggerSubroutine,
        MusicMessageSubroutine,
        MessageParsingSubroutine]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.register_local_subroutines(self)

    async def run(self, *args, **kwargs):
        while self.messages_queue:
            signal = await self.run_local_subroutines(self.messages_queue.pop(0))
            if signal:
                return signal


class CommandsProcessingSubroutine(BaseSubroutine[MediatorT, CommandsT]):

    local_subroutines = [
        CommandsSpamSubroutine,
        ExecuteCommandSubroutine]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.register_local_subroutines(self)

    async def run(self, *args, **kwargs):
        while self.commands_queue:
            message, (spec, values, flags) = self.commands_queue.pop(0)
            signal = await self.run_local_subroutines(message, spec, values, flags)
            if signal:
                return signal
