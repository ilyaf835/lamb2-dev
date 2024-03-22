from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List, Tuple, Union

from lamb.core.executor import Signal
from lamb.utils.tokenizer.exceptions import ParsingException


from bot.mods.spec import CommandSpec, FlagSpec
from bot.mods.spec.parser import CommandParser
from bot.mods.spec.exceptions import (
    ValueMissingError,
    ValueNotAllowedError,
    MultipleValuesError,
    AccessRightsError
)
from .base import BaseSubroutine

if TYPE_CHECKING:
    from bot.mods.chat.messages import AnyMessage


ParsedCommandTuple = Tuple[CommandSpec, List[str], Dict[FlagSpec, List[str]]]
ProcessedCommandTuple = Tuple[CommandSpec, List[str], Dict[str, Union[str, bool]]]


class SkipBotMessageSubroutine(BaseSubroutine):

    async def run(self, message: AnyMessage, *args, **kwargs):
        if self.mediator.profile.is_bot(message.user.name, message.user.tripcode):
            return Signal.SKIP


class MessageHooksTriggerSubroutine(BaseSubroutine):

    async def run(self, message: AnyMessage, *args, **kwargs):
        if message.type == 'join':
            self.mediator.hooks_workers.enqueue(
                self.hooks_manager.run_all, args=('on_join', message),
                exception_callbacks=[self.mediator.exception_callback])
        elif message.type == 'message':
            self.mediator.hooks_workers.enqueue(
                self.hooks_manager.run_all, args=('on_message', message),
                exception_callbacks=[self.mediator.exception_callback])


class MusicMessageSubroutine(BaseSubroutine):

    async def run(self, message: AnyMessage, *args, **kwargs):
        if message.type == 'music':
            if not self.mediator.player.paused:
                with self.mediator.locks.player:
                    self.mediator.player.pause()
                    self.mediator.player.reset_timestamp()
                self.mediator.send_message('Queue paused')


class MessageParsingSubroutine(BaseSubroutine):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        profile = self.mediator.profile
        self.permits = profile.permits
        self.command_parser = CommandParser(profile.commands, profile.settings['general']['command_prefix'])

    def check_spec(self, spec: CommandSpec | FlagSpec, values: list[str], permit: int):
        if spec.require_value is True and not values:
            raise ValueMissingError(format_args=(spec.name,))
        if spec.require_value is False and values:
            raise ValueNotAllowedError(format_args=(spec.name,))
        if not spec.multiple_values and values[1:]:
            raise MultipleValuesError(format_args=(spec.name,))
        if permit > self.permits[spec.permit]:
            raise AccessRightsError(format_args=(spec.name,))

    def process_commands(self, parsed_commands: list[ParsedCommandTuple], permit: int) -> list[ProcessedCommandTuple]:
        commands = []
        for command_spec, command_values, flags_dict in parsed_commands:
            self.check_spec(command_spec, command_values, permit)
            flags = {}
            for flag_spec, flag_values in flags_dict.items():
                self.check_spec(flag_spec, flag_values, permit)
                if flag_values:
                    flags[flag_spec.name] = ' '.join(flag_values)
                else:
                    flags[flag_spec.name] = True
            commands.append((command_spec, command_values, flags))

        return commands

    async def run(self, message: AnyMessage, *args, **kwargs):
        if message.type == 'message':
            user = message.user
            if self.mediator.profile.is_banned(user.name):
                return
            try:
                parsed_commands = self.command_parser.parse(message.text)
                processed_commands = self.process_commands(parsed_commands, self.mediator.user_permit(user))
            except ParsingException as error:
                self.mediator.send_error(error, user=self.mediator.to_user(message))
            else:
                for command in processed_commands:
                    self.commands_queue.append((message, command))
