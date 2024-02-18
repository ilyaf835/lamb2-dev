from __future__ import annotations
from typing import TypeVar, Any

from lamb.utils.threads import LocksProxy

from bot.mediator import Mediator as DefaultMediator
from bot.mediator import MessageSender
from bot.config import Config
from bot.mods.translator import Translator
from bot.mods.chat import Chat
from bot.mods.music import Player
from bot.mods.extractor import Extractor

from .profile import Profile


MediatorT = TypeVar('MediatorT', bound='Mediator')


class Mediator(DefaultMediator):

    def init(self, session: dict[str, Any], extractor_address: tuple[str, int], *args, **kwargs):
        self.config = Config()
        self.profile = Profile()
        self.profile.init(session)
        self.translator = Translator(
            self.profile.translations['labels'],
            self.profile.translations, self.profile.language)

        self.extractor = Extractor(extractor_address)
        self.player = Player(self.config.DURATION_LIMIT, self.config.QUEUE_LIMIT)
        self.chat = Chat()
        self.room = self.chat.room

        self.message_sender = MessageSender(self)
        self.locks = LocksProxy()
        self.whitelist_status = False
