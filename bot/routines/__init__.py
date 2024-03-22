from __future__ import annotations
from typing import TYPE_CHECKING

from lamb.core.bases import BaseRoutine
from lamb.core.managers import HooksManager

from .subroutines import (
    MessagesUpdatingSubroutine,
    MessagesProcessingSubroutine,
    CommandsProcessingSubroutine,
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
        MessagesUpdatingSubroutine,
        MessagesProcessingSubroutine,
        CommandsProcessingSubroutine]

    def __init__(self, mediator: MediatorT, commands: CommandsT,
                 hooks_manager: HooksManager, routines_manager: RoutinesManager, *args, **kwargs):
        super().__init__(mediator, commands, hooks_manager, routines_manager)

        self.messages_queue = []
        self.commands_queue = []
        self.register_subroutines(self)
