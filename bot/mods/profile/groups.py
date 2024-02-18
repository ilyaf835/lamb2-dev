from __future__ import annotations
from typing import Type, Any, Optional

from attrs import define, field, asdict

from .exceptions import (
    PermitNotExistsError,
    GroupNotExistsError,
    GroupTypeNotExistsError
)


@define
class BaseGroup:
    name: str
    permit: str
    type: str
    users: dict[str, Any] = field(factory=dict)
    info: dict[str, Any] = field(factory=dict)

    def add_user(self, *args, **kwargs):
        pass

    def remove_user(self, *args, **kwargs):
        pass


class GroupsManager:

    types: dict[str, Type[BaseGroup]]
    groups: dict[str, BaseGroup]

    def __init__(self, src: dict[str, Any], permits: dict[str, int],
                 types: Optional[dict[str, Type[BaseGroup]]] = None):
        self.groups_src = src
        self.permits = permits
        self.types = {}
        self.groups = {}
        if types:
            self.types.update(types)
        for params in src.values():
            self.add_group(**params)

    def update_types(self, types: dict[str, Type[BaseGroup]]):
        self.types.update(types)

    def get_group(self, name: str):
        try:
            return self.groups[name]
        except KeyError:
            raise GroupNotExistsError(format_args=(name,))

    def add_group(self, name: str, permit: str, type: str, **params):
        if permit not in self.permits:
            raise PermitNotExistsError(format_args=(permit,))
        if type not in self.types:
            raise GroupTypeNotExistsError(format_args=(type,))
        else:
            group = self.groups[name] = self.types[type](name, permit, type, **params)
            self.groups_src[name].update(asdict(group, recurse=False))

    def remove_group(self, name: str):
        self.groups.pop(name, None)

    def add_user(self, group: str, *args, **kwargs):
        return self.get_group(group).add_user(*args, **kwargs)

    def remove_user(self, group: str, *args, **kwargs):
        return self.get_group(group).remove_user(*args, **kwargs)
