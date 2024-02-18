from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from collections.abc import Iterable


class LambException(Exception):

    msg = ''

    def __init__(self, msg: str = '', format_args: Iterable[Any] = (),
                 format_kw: Optional[dict[str, Any]] = None):
        if format_kw is None:
            format_kw = {}
        if msg:
            self.msg = msg
        self.format_args = format_args
        self.format_kw = format_kw
        if self.msg is not None:
            super().__init__(self.msg.format(*format_args, **format_kw))


class ModException(LambException):
    pass


class CommandException(LambException):
    pass


class HookException(LambException):
    pass


class RoutineException(LambException):
    pass
