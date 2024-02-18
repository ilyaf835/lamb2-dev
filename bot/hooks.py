from __future__ import annotations
from typing import TYPE_CHECKING

from lamb.core.bases import BaseHook

from .mediator import MediatorT
from .commands import CommandsT

if TYPE_CHECKING:
    from .mods.chat.messages import JoinMessage, TextMessage


class WhitelistHook(BaseHook[MediatorT, CommandsT]):

    def on_join(self, message: JoinMessage, *args, **kwargs):
        user = message.user
        if (not self.mediator.whitelist_status
                or user.name in self.mediator.profile.whitelist
                or self.mediator.is_admin_user(user)
                or not self.mediator.room.is_host(self.mediator.bot_user)):
            return
        with self.mediator.locks.chat:
            self.mediator.room.kick(user)
            return True


class BlacklistHook(BaseHook[MediatorT, CommandsT]):

    def on_join(self, message: JoinMessage, *args, **kwargs):
        user = message.user
        if not (self.mediator.room.is_host(self.mediator.bot_user)
                and self.mediator.profile.ban_status(user.name) == 'permanent'):
            return
        with self.mediator.locks.chat:
            self.mediator.room.ban(user)
            return True


class PrivateMessageHook(BaseHook[MediatorT, CommandsT]):

    def on_message(self, message: TextMessage, *args, **kwargs):
        if message.private:
            if self.mediator.is_admin_user(message.user):
                return
            admin = self.mediator.admin_user
            if admin:
                self.mediator.send_message(f'{message.user.name}: {message.text}', user=admin)


class NoticeHook(BaseHook[MediatorT, CommandsT]):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.notified = {}

    def on_join(self, message: JoinMessage, *args, **kwargs):
        user = message.user
        if user.name not in self.notified:
            self.notified[user.name] = True
            self.mediator.send_message(self.mediator.config.HELP_MESSAGE, user=user)
