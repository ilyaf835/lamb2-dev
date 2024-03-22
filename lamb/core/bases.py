from __future__ import annotations
from typing import Generic, Protocol, Type, TypeVar, Optional

from .executor import Signal, RoutinesExecutor
from .managers import HooksManager, RoutinesManager


BaseMediatorT = TypeVar('BaseMediatorT', bound='BaseMediator')
BaseCommandsT = TypeVar('BaseCommandsT', bound='BaseCommands')


class BaseEntity(Protocol):
    name: str


class BaseWrapper(Protocol):
    def __init__(self, entity: BaseEntity): ...
    def __getattr__(self, name: str): ...


class BaseHookWrapper(BaseWrapper):

    def __init__(self, hook: BaseHook):
        self.hook = hook

    def __getattr__(self, name: str):
        return getattr(self.hook, name)


class BaseRoutineWrapper(BaseWrapper):

    def __init__(self, routine: BaseRoutine):
        self.routine = routine

    def __getattr__(self, name: str):
        return getattr(self.routine, name)

    async def run(self, *args, **kwargs) -> Optional[Signal | str]:
        raise NotImplementedError


class BaseHook(BaseEntity, Generic[BaseMediatorT, BaseCommandsT]):

    def __init__(self, mediator: BaseMediatorT, commands: BaseCommandsT):
        self.mediator = mediator
        self.commands = commands

    @property
    def name(self):
        return self.__class__.__name__


class BaseRoutine(BaseEntity, Generic[BaseMediatorT, BaseCommandsT]):

    subroutines_manager_cls: Type[RoutinesManager] = RoutinesManager
    subroutines_wrappers: dict[str, Type[BaseRoutineWrapper]] = {}
    subroutines: list[Type[BaseRoutine[BaseMediatorT, BaseCommandsT]]] = []
    local_subroutines: list[Type[BaseRoutine[BaseMediatorT, BaseCommandsT]]] = []

    def __init__(self, mediator: BaseMediatorT, commands: BaseCommandsT,
                 hooks_manager: HooksManager, routines_manager: RoutinesManager, *args, **kwargs):
        self.mediator = mediator
        self.commands = commands
        self.hooks_manager = hooks_manager
        self.routines_manager = routines_manager
        self.subroutines_manager = self.subroutines_manager_cls(wrappers=self.subroutines_wrappers)
        self.local_subroutines_manager = self.subroutines_manager_cls(wrappers=self.subroutines_wrappers)

    @property
    def name(self):
        return self.__class__.__name__

    def register_subroutines(self, *args, **kwargs):
        for subroutine in self.subroutines:
            self.subroutines_manager.register(subroutine(
                self.mediator, self.commands, self.hooks_manager, self.routines_manager, *args, **kwargs))

    def register_local_subroutines(self, *args, **kwargs):
        for subroutine in self.local_subroutines:
            self.local_subroutines_manager.register(subroutine(
                self.mediator, self.commands, self.hooks_manager, self.routines_manager, *args, **kwargs))

    async def run_local_subroutines(self, *args, **kwargs):
        for container in self.local_subroutines_manager.yield_routines():
            signal = await container.run_method(*args, **kwargs)
            if signal:
                if signal == Signal.SKIP:
                    break
                return signal

    async def run(self, *args, **kwargs) -> Optional[Signal | str]:
        pass


class BaseMediator:

    def __init__(self, *args, **kwargs):
        pass


class BaseCommands(Generic[BaseMediatorT]):

    def __init__(self, mediator: BaseMediatorT, *args, **kwargs):
        self.mediator = mediator


class BaseSignals(Generic[BaseMediatorT, BaseCommandsT]):

    def __init__(self, mediator: BaseMediatorT, commands: BaseCommandsT,
                 hooks_manager: HooksManager, routines_manager: RoutinesManager):
        self.mediator = mediator
        self.commands = commands
        self.hooks_manager = hooks_manager
        self.routines_manager = routines_manager


class BaseSetup:

    mediator_cls: Type[BaseMediator] = BaseMediator
    commands_cls: Type[BaseCommands] = BaseCommands
    signals_cls: Type[BaseSignals] = BaseSignals
    executor_cls: Type[RoutinesExecutor] = RoutinesExecutor

    hooks_manager_cls: Type[HooksManager] = HooksManager
    routines_manager_cls: Type[RoutinesManager] = RoutinesManager

    hooks: list[Type[BaseHook]] = []
    hooks_wrappers: dict[str, Type[BaseHookWrapper]] = {}

    routines: list[Type[BaseRoutine]] = []
    routines_wrappers: dict[str, Type[BaseRoutineWrapper]] = {}

    def bootstrap(self, *args, **kwargs):
        self.hooks_manager = self.hooks_manager_cls()
        self.routines_manager = self.routines_manager_cls()
        self.bootstrap_mediator()
        self.bootstrap_commands()
        self.bootstrap_signals()
        self.bootstrap_executor()
        self.bootstrap_hooks()
        self.bootstrap_routines()

    def bootstrap_mediator(self, *args, **kwargs):
        self.mediator = self.mediator_cls()

    def bootstrap_commands(self, *args, **kwargs):
        self.commands = self.commands_cls(self.mediator)

    def bootstrap_hooks(self, *args, **kwargs):
        self.hooks_manager.update_wrappers(self.hooks_wrappers)
        for hook in self.hooks:
            self.hooks_manager.register(hook(self.mediator, self.commands))

    def bootstrap_routines(self, *args, **kwargs):
        self.routines_manager.update_wrappers(self.routines_wrappers)
        for routine in self.routines:
            self.routines_manager.register(
                routine(self.mediator, self.commands, self.hooks_manager, self.routines_manager))

    def bootstrap_signals(self, *args, **kwargs):
        self.signals = self.signals_cls(self.mediator, self.commands, self.hooks_manager, self.routines_manager)

    def bootstrap_executor(self, *args, **kwargs):
        self.executor = self.executor_cls(
            self.mediator, self.commands, self.hooks_manager, self.routines_manager, self.signals)
