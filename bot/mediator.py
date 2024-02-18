from __future__ import annotations
from typing import TYPE_CHECKING, TypeVar, Any, Optional

import time

from lamb.core.bases import BaseMediator
from lamb.utils.threads import LocksProxy, ThreadsHandler

from .config import Config
from .mods.profile import Profile
from .mods.chat import Chat
from .mods.music import Player
from .mods.translator import Translator
from .mods.extractor import Extractor

if TYPE_CHECKING:
    from collections.abc import Iterable

    from lamb.exceptions import LambException
    from .mods.chat import User
    from .mods.chat.messages import TextMessage


MediatorT = TypeVar('MediatorT', bound='Mediator')


class MessageSender:

    def __init__(self, mediator: Mediator):
        self.config = mediator.config
        self.room = mediator.room
        self.translator = mediator.translator
        self.send_worker = ThreadsHandler(workers_count=1, start=True)
        self.timestamp = 0

    def send(self, msg: str, user: Optional[User] = None, url: Optional[str] = None):
        remaining = self.config.SEND_DELAY - (time.monotonic() - self.timestamp)
        if remaining > 0:
            time.sleep(remaining)
        self.room.send_message(msg, user=user, url=url)
        self.timestamp = time.monotonic()

    def send_message(self, msg: str, format_args: Iterable[Any] = (), format_kw: Optional[dict[str, Any]] = None,
                     user: Optional[User] = None, url: Optional[str] = None, translate: bool = True):
        if format_kw is None:
            format_kw = {}
        if translate:
            msg = self.translator.translate(msg)
        self.send_worker.enqueue(self.send, args=(msg.format(*format_args, **format_kw), user, url))

    def send_error(self, error: LambException, user: Optional[User] = None,
                   url: Optional[str] = None, translate: bool = True):
        self.send_message(error.msg, error.format_args, error.format_kw, user=user, url=url, translate=translate)


class Mediator(BaseMediator):

    def init(self, profile_dict: dict[str, Any], extractor_address: tuple[str, int], *args, **kwargs):
        self.config = Config()
        self.profile = Profile()
        self.profile.init(profile_dict)
        self.translator = Translator(
            self.profile.translations.pop('labels'),
            self.profile.translations, self.profile.language)

        self.extractor = Extractor(extractor_address)
        self.player = Player(self.config.DURATION_LIMIT, self.config.QUEUE_LIMIT)
        self.chat = Chat()
        self.room = self.chat.room

        self.message_sender = MessageSender(self)
        self.locks = LocksProxy()
        self.whitelist_status = False

    def is_player_available(self):
        with self.locks.chat:
            return self.room.music and (not self.room.dj_mode or self.room.is_host(self.bot_user))

    @property
    def admin_user(self):
        with self.locks.chat:
            return self.room.get_user(self.profile.admin['name'])

    @property
    def bot_user(self):
        with self.locks.chat:
            return self.room.get_user_or_raise(self.profile.bot['name'])

    def is_admin_user(self, user: User):
        return self.profile.is_admin(user.name, user.tripcode)

    def is_bot_user(self, user: User):
        return self.profile.is_bot(user.name, user.tripcode)

    def user_permit(self, user: User):
        with self.locks.groups:
            return self.profile.user_permit(user.name, user.tripcode)

    def check_permit(self, group: str, user: User):
        with self.locks.groups:
            return self.profile.check_permit(group, user.name, user.tripcode)

    def add_user_to_group(self, group: str, user: User):
        with self.locks.groups:
            self.profile.groups_manager.add_user(group, user.name, user.tripcode)

    def remove_user_from_group(self, group: str, user: User):
        with self.locks.groups:
            self.profile.groups_manager.remove_user(group, user.name)

    def switch_whitelist_status(self):
        self.whitelist_status ^= True

        return self.whitelist_status

    def give_host(self, user: User):
        with self.locks.chat:
            if self.room.is_host(self.bot_user):
                self.room.give_host(user)

    @staticmethod
    def to_user(message: TextMessage):
        return message.user if message.private else None

    def send_message(self, msg: str, format_args: Iterable[Any] = (), format_kw: Optional[dict[str, Any]] = None,
                     user: Optional[User] = None, url: Optional[str] = None, translate: bool = True):
        self.message_sender.send_message(msg, format_args, format_kw, user, url, translate)

    def send_error(self, error: LambException, user: Optional[User] = None,
                   url: Optional[str] = None, translate: bool = True):
        self.message_sender.send_error(error, user, url, translate)
