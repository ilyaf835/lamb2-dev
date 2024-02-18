from __future__ import annotations
from typing import TYPE_CHECKING

import sys
import time
import traceback

from lamb.core.executor import Signal
from lamb.exceptions import ModException, CommandException
from lamb.context.exceptions import ContextException

from .base import BaseSubroutine

if TYPE_CHECKING:
    from collections.abc import Callable

    from lamb.exceptions import LambException
    from bot.mods.spec import CommandSpec
    from bot.mods.chat.messages import TextMessage


class CommandsSpamSubroutine(BaseSubroutine):

    DELAY: int = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.timestamps = {}

    def run(self, message: TextMessage, *args, **kwargs):
        user = message.user
        if not self.mediator.is_admin_user(user):
            now = time.monotonic()
            timestamp = self.timestamps.setdefault(user, now)
            if now >= timestamp:
                self.timestamps[user] = now + self.DELAY
            else:
                self.mediator.send_message("Don't spam commands", user=self.mediator.to_user(message))
                return Signal.SKIP


class ExecuteCommandSubroutine(BaseSubroutine):

    def send_error(self, message: TextMessage, spec: CommandSpec, error: LambException):
        user = None
        if message.private and self.mediator.is_admin_user(message.user):
            user = message.user
        if error.msg:
            self.mediator.send_error(error, user=user)
        else:
            self.mediator.send_message(
                'Unexpected error while executing command <{}>', format_args=(spec.name,), user=user)

    def execute_command(self, command_func: Callable, message: TextMessage,
                        spec: CommandSpec, values: list[str], flags: dict[str, str | bool]):
        try:
            if not spec.batch_values and values:
                for value in values:
                    command_func(message, spec, value, **flags)
            else:
                command_func(message, spec, *values, **flags)
        except (CommandException, ContextException) as e:
            self.send_error(message, spec, e)
        except ModException as e:
            traceback.print_exception(e.__class__, e, e.__traceback__, file=sys.stdout)
            self.send_error(message, spec, e)

    def handle_command(self, message: TextMessage, spec: CommandSpec,
                       values: list[str], flags: dict[str, str | bool]):
        command_func = getattr(self.commands, spec.name)
        if not spec.threaded:
            self.execute_command(command_func, message, spec, values, flags)
        else:
            self.commands_workers.enqueue(
                self.execute_command, args=(command_func, message, spec, values, flags),
                exception_callbacks=[self.exception_callback])

    def run(self, message: TextMessage, spec: CommandSpec,
            values: list[str], flags: dict[str, str | bool], *args, **kwargs):
        self.handle_command(message, spec, values, flags)
        if spec.signal:
            return spec.signal
