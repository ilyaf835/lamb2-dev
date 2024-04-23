from __future__ import annotations
from typing import TypeVar, Any

from lamb.utils.threads import LocksProxy, ThreadsHandler

from bot.mediator import Mediator as DefaultMediator
from bot.mediator import MessagesSender, MusicPlayer
from bot.config import Config
from bot.mods.translator import Translator
from bot.mods.chat import Chat
from bot.mods.music import Player
from bot.mods.extractor import Extractor

from .profile import Profile


MediatorT = TypeVar('MediatorT', bound='Mediator')


class Mediator(DefaultMediator):

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
