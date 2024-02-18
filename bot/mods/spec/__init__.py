from __future__ import annotations
from typing import Any, Optional

import copy
from attrs import define, field


@define
class CommandSpec:
    name: str
    permit: str
    aliases: list[str] = field(factory=list)
    flags: dict[str, FlagSpec] = field(factory=dict)

    require_value: bool = False
    multiple_values: bool = False
    batch_values: bool = False

    threaded: bool = True
    signal: Optional[str] = None


@define
class FlagSpec:
    name: str
    permit: str
    aliases: list[str] = field(factory=list)

    require_value: bool = False
    multiple_values: bool = False


def process_spec(src: dict[str, Any], command_spec=CommandSpec,
                 flag_spec=FlagSpec, is_flags=False) -> dict[str, CommandSpec]:
    spec_dict = {}
    for name, params in copy.deepcopy(src).items():
        flags = params.get('flags')
        if flags:
            params['flags'] = process_spec(flags, command_spec, flag_spec, is_flags=True)

        if is_flags:
            spec = flag_spec(name, **params)
        else:
            spec = command_spec(name, **params)

        if name not in spec.aliases:
            spec.aliases.append(name)
        for alias in spec.aliases:
            spec_dict[alias] = spec

    return spec_dict
