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


class MessagesSender:

    def __init__(self, mediator: Mediator):
        self.mediator = mediator
        self.config = mediator.config
        self.room = mediator.room
        self.translator = mediator.translator
        self.messages_worker = mediator.messages_worker
        self.timestamp = 0.0

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
        self.messages_worker.enqueue(self.send, args=(msg.format(*format_args, **format_kw), user, url),
                                     exception_callbacks=[self.mediator.exception_callback])

    def send_error(self, error: LambException, user: Optional[User] = None,
                   url: Optional[str] = None, translate: bool = True):
        self.send_message(error.msg, error.format_args, error.format_kw, user=user, url=url, translate=translate)


class MusicPlayer:

    def __init__(self, mediator: Mediator):
        self.mediator = mediator
        self.locks = mediator.locks
        self.player = mediator.player
        self.room = mediator.room
        self.player_worker = mediator.player_worker

    def start(self):
        self.player_worker.enqueue(self.loop_player, exception_callbacks=[self.mediator.exception_callback])

    def stop(self):
        self.player_worker.stop()

    def is_playing(self):
        if self.player.current_track:
            return time.monotonic() < self.player.timestamp + self.player.current_track.duration
        return False

    def pop_track(self):
        if self.player.repeat:
            return self.player.current_track or self.player.pop_track()
        else:
            return self.player.pop_track()

    def loop_player(self):
        while True:
            time.sleep(0.2)
            if not self.mediator.is_player_available():
                continue
            with self.locks.player:
                if self.player.paused or self.is_playing():
                    continue
                if not self.player.queue:
                    self.player.current_track = None
                else:
                    track = self.player.current_track = self.pop_track()
                    self.room.launch_player(track.title, track.stream_url)
                    self.player.set_timestamp()


class Mediator(BaseMediator):

    threads_exceptions: list[BaseException]

    def init(self, profile_dict: dict[str, Any], extractor_address: tuple[str, int], *args, **kwargs):
        self.locks = LocksProxy()
        self.threads_exceptions = []

        self.config = Config()
        self.profile = Profile()
        self.profile.init(profile_dict)
        self.translator = Translator(
            self.profile.translations['labels'],
            self.profile.translations, self.profile.language)

        self.commands_workers = ThreadsHandler(workers_count=self.config.COMMANDS_THREADS, start=True)
        self.hooks_workers = ThreadsHandler(workers_count=self.config.HOOKS_THREADS, start=True)
        self.player_worker = ThreadsHandler(workers_count=self.config.PLAYER_THREADS, start=True)
        self.messages_worker = ThreadsHandler(workers_count=self.config.MESSAGES_THREADS, start=True)

        self.extractor = Extractor(extractor_address)
        self.player = Player(self.config.DURATION_LIMIT, self.config.QUEUE_LIMIT)
        self.chat = Chat()
        self.room = self.chat.room

        self.whitelist_status = False

        self.messages_sender = MessagesSender(self)
        self.music_player = MusicPlayer(self)
        self.music_player.start()

    def exception_callback(self, exc: BaseException):
        self.threads_exceptions.append(exc)

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
        self.messages_sender.send_message(msg, format_args, format_kw, user, url, translate)

    def send_error(self, error: LambException, user: Optional[User] = None,
                   url: Optional[str] = None, translate: bool = True):
        self.messages_sender.send_error(error, user, url, translate)
