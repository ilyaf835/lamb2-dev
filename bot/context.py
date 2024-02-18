from __future__ import annotations
from typing import TYPE_CHECKING

from lamb.context import context_descriptor, States
from lamb.context.exceptions import ContextException

if TYPE_CHECKING:
    from .mediator import Mediator
    from .mods.chat.messages import TextMessage
    from .mods.spec import CommandSpec


class CommandsContext:

    def __init__(self, mediator: Mediator):
        self.mediator = mediator
        self.states = States()

    @context_descriptor
    def dj_mode(self, command_meth, message: TextMessage, spec: CommandSpec, *values, **flags):
        with self.mediator.locks.dj_state:
            if self.states.dj and not self.mediator.check_permit('dj', message.user):
                raise ContextException('Not enough rights to use this command in dj mode')

        return command_meth(message, spec, *values, **flags)

    @context_descriptor
    def require_host(self, command_meth, message: TextMessage, spec: CommandSpec, *values, **flags):
        if not self.mediator.room.is_host(self.mediator.bot_user):
            raise ContextException('Bot must be host to execute this command')

        return command_meth(message, spec, *values, **flags)

    @context_descriptor
    def require_player(self, command_meth, message: TextMessage, spec: CommandSpec, *values, **flags):
        if not self.mediator.is_player_available():
            raise ContextException('Player not available in this room')

        return command_meth(message, spec, *values, **flags)
