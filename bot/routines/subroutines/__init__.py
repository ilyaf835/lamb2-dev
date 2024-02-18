import time

from lamb.utils.threads import ThreadsHandler

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


class ExceptionsSentinelSubroutine(BaseSubroutine[MediatorT, CommandsT]):

    def run(self, *args, **kwargs):
        if self.threads_exceptions:
            raise self.threads_exceptions[0]


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

    def run(self, *args, **kwargs):
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

    def run(self, *args, **kwargs):
        while self.messages_queue:
            signal = self.run_local_subroutines(self.messages_queue.pop(0))
            if signal:
                return signal


class CommandsProcessingSubroutine(BaseSubroutine[MediatorT, CommandsT]):

    local_subroutines = [
        CommandsSpamSubroutine,
        ExecuteCommandSubroutine]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.register_local_subroutines(self)

    def run(self, *args, **kwargs):
        while self.commands_queue:
            message, (spec, values, flags) = self.commands_queue.pop(0)
            signal = self.run_local_subroutines(message, spec, values, flags)
            if signal:
                return signal


class MusicPlayerRoutine(BaseSubroutine[MediatorT, CommandsT]):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.locks = self.mediator.locks
        self.player = self.mediator.player
        self.room = self.mediator.room
        self.player_worker = ThreadsHandler(workers_count=1, start=True)
        self.player_worker.enqueue(self.launch_player, exception_callbacks=[self.exception_callback])

    def is_playing(self):
        if self.player.current_track:
            return time.monotonic() < self.player.timestamp + self.player.current_track.duration
        return False

    def pop_track(self):
        if self.player.repeat:
            return self.player.current_track or self.player.pop_track()
        else:
            return self.player.pop_track()

    def launch_player(self):
        while True:
            time.sleep(0.2)
            if not self.mediator.is_player_available():
                continue
            with self.locks.player:
                if self.player.paused or self.is_playing():
                    continue
                if not self.player.queue:
                    self.player.current_track = None
                else:
                    track = self.player.current_track = self.pop_track()
                    self.room.launch_player(track.title, track.stream_url)
                    self.player.set_timestamp()
