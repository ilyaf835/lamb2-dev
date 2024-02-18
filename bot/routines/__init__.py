from __future__ import annotations
from typing import TYPE_CHECKING

from lamb.core.bases import BaseRoutine
from lamb.core.managers import HooksManager
from lamb.utils.threads import ThreadsHandler

from .subroutines import (
    ExceptionsSentinelSubroutine,
    MessagesUpdatingSubroutine,
    MessagesProcessingSubroutine,
    CommandsProcessingSubroutine,
    MusicPlayerRoutine
)
from ..mediator import MediatorT
from ..commands import CommandsT

if TYPE_CHECKING:
    from lamb.core.managers import  HooksManager, RoutinesManager
    from .subroutines.messages import ProcessedCommandTuple
    from ..mods.chat.messages import TextMessage, AnyMessage


class ChatRoutine(BaseRoutine[MediatorT, CommandsT]):

    messages_queue: list[AnyMessage]
    commands_queue: list[tuple[TextMessage, ProcessedCommandTuple]]
    threads_exceptions: list[BaseException]

    subroutines = [
        ExceptionsSentinelSubroutine,
        MessagesUpdatingSubroutine,
        MessagesProcessingSubroutine,
        CommandsProcessingSubroutine,
        MusicPlayerRoutine]

    def __init__(self, mediator: MediatorT, commands: CommandsT,
                 hooks_manager: HooksManager, routines_manager: RoutinesManager, *args, **kwargs):
        super().__init__(mediator, commands, hooks_manager, routines_manager)

        self.messages_queue = []
        self.commands_queue = []
        self.threads_exceptions = []

        config = self.mediator.config
        self.commands_workers = ThreadsHandler(workers_count=config.COMMANDS_THREADS, start=True)
        self.hooks_workers = ThreadsHandler(workers_count=config.HOOKS_THREADS, start=True)
        self.register_subroutines(self)

    def exception_callback(self, exc: BaseException):
        self.threads_exceptions.append(exc)
