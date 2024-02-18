from __future__ import annotations
from typing import TYPE_CHECKING

from lamb.utils.tokenizer import create_parser

from .exceptions import NoSuchCommandError, NoSuchFlagError

if TYPE_CHECKING:
    from ..spec import CommandSpec, FlagSpec


class CommandParser:

    def __init__(self, commands_dict: dict[str, CommandSpec], command_prefix: str):
        self.parse_tokens = create_parser(command_prefix)
        self.commands_dict = commands_dict

    def parse(self, s: str) -> list[tuple[CommandSpec, list[str], dict[FlagSpec, list[str]]]]:
        output = []
        tokens = self.parse_tokens(s)
        if not tokens:
            return output

        for command, command_values, raw_flags in tokens:
            command_spec = self.commands_dict.get(command)
            if not command_spec:
                raise NoSuchCommandError(format_args=(command,))

            flags = {}
            for flag, flag_values in raw_flags:
                flag_spec = command_spec.flags.get(flag)
                if not flag_spec:
                    raise NoSuchFlagError(format_args=(flag,))

                flags[flag_spec] = flag_values

            output.append((command_spec, command_values, flags))

        return output
