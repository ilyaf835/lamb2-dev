from __future__ import annotations
from typing import TYPE_CHECKING, Any, Type, Optional

from bot import DefaultSetup
from bot.mods.chat.exceptions import ChatException

from .mediator import Mediator

if TYPE_CHECKING:
    from selectors import BaseSelector


class BotSetup(DefaultSetup):

    mediator_cls: Type[Mediator] = Mediator

    def __init__(self, profile_dict: dict[str, Any], extractor_address: tuple[str, int],
                 sentinel_selector: BaseSelector, correlation_key: Any):
        super().__init__(profile_dict, extractor_address)
        self.sentinel_selector = sentinel_selector
        self.correlation_key = correlation_key

    def bootstrap_executor(self, *args, **kwargs):
        self.executor = self.executor_cls(
            self.mediator, self.commands, self.hooks_manager, self.routines_manager,
            self.signals, self.sentinel_selector, self.correlation_key)


class Bot:

    setup_cls: type[BotSetup] = BotSetup

    def __init__(self, profile_dict: dict[str, Any], extractor_address: tuple[str, int],
                 sentinel_selector: BaseSelector, correlation_key: Any):
        self.setup = self.setup_cls(profile_dict, extractor_address, sentinel_selector, correlation_key)
        self.setup.bootstrap()

        self.executor = self.setup.executor
        self.mediator = self.setup.mediator
        self.profile = self.mediator.profile
        self.config = self.mediator.config
        self.chat = self.mediator.chat
        self.room = self.mediator.room
        self.extractor = self.mediator.extractor

    def login(self):
        bot = self.profile.bot
        self.chat.login(bot['name'], passcode=bot['passcode'], icon=bot['icon'])
        bot['tripcode'] = self.chat.get_lounge_json()['profile'].get('tripcode', '')

    def logout(self):
        self.chat.logout()

    def join_room(self, url: str):
        self.chat.join_room(url)

    def leave_room(self):
        self.chat.leave_room()

    def return_host(self):
        if self.room.connected:
            try:
                admin = self.mediator.admin_user
                if admin:
                    self.mediator.give_host(admin)
            except ChatException:
                pass

    @property
    def running(self):
        return self.executor.running

    def run_once(self, timeout: Optional[float] = 0):
        self.executor.start()
        self.executor.run_once(timeout=timeout)

    def shutdown(self):
        self.executor.shutdown()
        self.mediator.commands_workers.stop()
        self.mediator.hooks_workers.stop()
        self.mediator.player_worker.stop()
        self.mediator.messages_worker.stop()
