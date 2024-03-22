from __future__ import annotations
from typing import Any, Type

from lamb.core.bases import BaseSetup
from lamb.core.executor import RoutinesExecutor

from bot.commands import Commands
from bot.hooks import WhitelistHook, BlacklistHook, PrivateMessageHook, NoticeHook

from bot.mods.chat.exceptions import ChatException

from .mediator import Mediator
from .routines import ChatRoutine


class DefaultSetup(BaseSetup):

    mediator_cls: Type[Mediator] = Mediator
    commands_cls: Type[Commands] = Commands
    executor_cls: Type[RoutinesExecutor] = RoutinesExecutor

    hooks = [
        WhitelistHook,
        BlacklistHook,
        PrivateMessageHook,
        NoticeHook]
    routines = [ChatRoutine]

    def __init__(self, session: dict[str, Any], extractor_address: tuple[str, int]):
        self.session = session
        self.extractor_address = extractor_address

    def bootstrap_mediator(self):
        self.mediator = self.mediator_cls()
        self.mediator.init(self.session, self.extractor_address)


class Bot:

    setup_cls: Type[DefaultSetup] = DefaultSetup

    def __init__(self, session: dict[str, Any], extractor_address: tuple[str, int], *args, **kwargs):
        self.setup = self.setup_cls(session, extractor_address)
        self.setup.bootstrap()

        self.executor = self.setup.executor
        self.mediator = self.setup.mediator
        self.profile = self.mediator.profile
        self.chat = self.mediator.chat
        self.room = self.mediator.room
        self.extractor = self.mediator.extractor

    def login(self):
        bot = self.profile.bot
        self.chat.login(bot['name'], passcode=bot['passcode'], icon=bot['icon'])
        bot['tripcode'] = self.chat.get_lounge_json()['profile'].get('tripcode')

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

    def start(self):
        self.executor.start()

    def shutdown(self):
        self.executor.shutdown()
        self.mediator.commands_workers.stop()
        self.mediator.hooks_workers.stop()
        self.mediator.player_worker.stop()
        self.mediator.messages_worker.stop()

    def run_once(self):
        self.executor.run_once(timeout=0)
