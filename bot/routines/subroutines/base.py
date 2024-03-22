from __future__ import annotations
from typing import TYPE_CHECKING

from lamb.core.bases import BaseRoutine

from bot.mediator import MediatorT
from bot.commands import CommandsT

if TYPE_CHECKING:
    from lamb.core.managers import HooksManager, RoutinesManager
    from bot.routines import ChatRoutine


class BaseSubroutine(BaseRoutine[MediatorT, CommandsT]):

    def __init__(self, mediator: MediatorT, commands: CommandsT,
                 hooks_manager: HooksManager, routines_manager: RoutinesManager,
                 routine: ChatRoutine, *args, **kwargs):
        super().__init__(mediator, commands, hooks_manager, routines_manager)

        self.messages_queue = routine.messages_queue
        self.commands_queue = routine.commands_queue
