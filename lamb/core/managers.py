from __future__ import annotations
from typing import TYPE_CHECKING, Generic, Type, TypeVar, Optional

if TYPE_CHECKING:
    from collections.abc import Callable

    from .bases import (
        BaseEntity,
        BaseWrapper,
        BaseHook,  # noqa: F401
        BaseHookWrapper,
        BaseRoutine,  # noqa: F401
        BaseRoutineWrapper
    )


EntityT = TypeVar('EntityT', bound='BaseEntity')
WrapperT = TypeVar('WrapperT', bound='BaseWrapper')


class BaseEntityContainer(Generic[EntityT, WrapperT]):

    def __init__(self, entity: EntityT, wrapper_cls: Optional[Type[WrapperT]] = None):
        self.entity = entity
        self.wrapper_cls = wrapper_cls
        if wrapper_cls:
            self.wrapped_entity = wrapper_cls(entity)
        else:
            self.wrapped_entity = None

    def set_wrapper(self, wrapper_cls: Type[WrapperT]):
        self.wrapper_cls = wrapper_cls
        self.wrapped_entity = wrapper_cls(self.entity)

    def remove_wrapper(self):
        self.wrapper_cls = None
        self.wrapped_entity = None


class BaseEntitiesManager(Generic[EntityT, WrapperT]):

    container_cls: Type[BaseEntityContainer]
    entities: dict[str, BaseEntityContainer]
    wrappers: dict[str, Type[BaseWrapper]]

    def __init__(self, wrappers: Optional[dict[str, Type[WrapperT]]] = None):
        self.entities = {}
        self.wrappers = {}
        if wrappers:
            self.wrappers.update(wrappers)

    def register(self, entity: EntityT, name: Optional[str] = None, wrapper_name: Optional[str] = None):
        if wrapper_name:
            wrapper_cls = self.wrappers[wrapper_name]
        else:
            wrapper_cls = None
        self.entities[name if name else entity.name] = self.container_cls(entity, wrapper_cls)

    def unregister(self, name: str):
        return self.entities.pop(name)

    def update_wrappers(self, wrappers: dict[str, Type[WrapperT]]):
        self.wrappers.update(wrappers)

    def wrap(self, entity_name: str, wrapper_name: str):
        self.entities[entity_name].set_wrapper(self.wrappers[wrapper_name])

    def unwrap(self, entity_name: str):
        self.entities[entity_name].remove_wrapper()


class HookContainer(BaseEntityContainer['BaseHook', 'BaseHookWrapper']):

    @property
    def hook(self):
        return self.entity

    def get_method(self, meth_name: str) -> Optional[Callable]:
        if self.wrapped_entity:
            return getattr(self.wrapped_entity, meth_name, None)
        else:
            return getattr(self.entity, meth_name, None)


class HooksManager(BaseEntitiesManager['BaseHook', 'BaseHookWrapper']):

    container_cls: Type[HookContainer] = HookContainer
    entities: dict[str, HookContainer]
    wrappers: dict[str, Type[BaseHookWrapper]]

    @property
    def hooks(self):
        return self.entities

    def run_all(self, meth_name: str, *args, **kwargs):
        for hook_container in self.hooks.values():
            meth = hook_container.get_method(meth_name)
            if meth:
                skip = meth(*args, **kwargs)
                if skip:
                    break


class RoutineContainer(BaseEntityContainer['BaseRoutine', 'BaseRoutineWrapper']):

    @property
    def routine(self):
        return self.entity

    @property
    def wrapper(self):
        return self.wrapped_entity

    @property
    def run_method(self):
        if self.wrapped_entity:
            return self.wrapped_entity.run
        else:
            return self.entity.run


class RoutinesManager(BaseEntitiesManager['BaseRoutine', 'BaseRoutineWrapper']):

    container_cls: Type[RoutineContainer] = RoutineContainer
    entities: dict[str, RoutineContainer]
    wrappers: dict[str, Type[BaseRoutineWrapper]]

    @property
    def routines(self):
        return self.entities

    def yield_routines(self):
        for key in self.routines.copy():
            try:
                yield self.routines[key]
            except KeyError:
                continue
