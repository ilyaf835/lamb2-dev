from __future__ import annotations
from typing import TYPE_CHECKING, TypeVar, Optional

from lamb.core.bases import BaseCommands
from lamb.exceptions import CommandException

from .mediator import MediatorT
from .context import CommandsContext

if TYPE_CHECKING:
    from .mods.music import Track
    from .mods.spec import CommandSpec
    from .mods.chat.messages import TextMessage


CommandsT = TypeVar('CommandsT', bound='Commands')


def get_page(src: list, page: int, page_size: int = 5):
    return src[page*page_size-page_size:page*page_size]


def enumerate_page(src: list, page: int, page_size: int = 5):
    return enumerate(get_page(src, page, page_size), page*page_size-(page_size-1))


def shorten(s: str, size: int = 20, end:str = '…'):
    if size < len(s.strip()):
        return s[:size].strip() + end
    else:
        return s[:size].strip()


def queue_message(queue: list[Track], page: int , page_size: int = 3):
    formatted = ''
    for index, track in enumerate_page(queue, page, page_size):
        formatted += f'{index}. {shorten(track.title)}\n' \
                     f'youtu.be/{track.origin_id}\n'

    return formatted.strip()


def search_message(results: list[Track]):
    formatted = ''
    for index, track in enumerate(results, 1):
        formatted += f'{index}. {shorten(track.title)}\n' \
                     f'youtu.be/{track.origin_id}\n'

    return formatted.strip()


def validate_index(index: str, min_index: int = 1, max_index: float = float('inf'), error_msg=''):
    try:
        vindex = int(index)
    except ValueError:
        raise CommandException(error_msg)
    if min_index > vindex or vindex > max_index:
        raise CommandException(error_msg)

    return vindex


class Commands(BaseCommands[MediatorT]):

    ctx = CommandsContext

    def __init__(self, mediator: MediatorT, *args, **kwargs):
        super().__init__(mediator, *args, **kwargs)
        self.context = self.ctx(mediator)
        self.locks = self.mediator.locks

        self.profile = self.mediator.profile
        self.extractor = self.mediator.extractor
        self.player = self.mediator.player
        self.chat = self.mediator.chat
        self.room = self.chat.room

        self.search_list = []

    def help(self, message: TextMessage, spec: CommandSpec,
             name: Optional[str] = None, public: bool = False):
        user = message.user
        is_moder = self.mediator.check_permit('moder', user)
        with self.locks.chat:
            if is_moder:
                if name:
                    user = self.room.get_user_or_raise(name)
                elif public:
                    user = None
        self.mediator.send_message(self.mediator.config.HELP_MESSAGE, user=user)

    def leave(self, message: TextMessage, spec: CommandSpec):
        with self.locks.chat:
            admin = self.mediator.admin_user
            if admin:
                self.mediator.give_host(admin)
            self.chat.leave_room()

    @ctx.require_host
    def give_host(self, message: TextMessage, spec: CommandSpec, name: Optional[str] = None):
        with self.locks.chat:
            if name:
                user = self.room.get_user_or_raise(name)
            else:
                user = self.mediator.admin_user
            if user:
                self.mediator.give_host(user)

    def add_moder(self, message: TextMessage, spec: CommandSpec, name: str):
        with self.locks.chat:
            user = self.room.get_user_or_raise(name)
        self.mediator.add_user_to_group('moder', user)

    def remove_moder(self, message: TextMessage, spec: CommandSpec, name: str):
        with self.locks.groups:
            self.mediator.profile.groups_manager.remove_user('moder', name)

    def add_dj(self, message: TextMessage, spec: CommandSpec, name: str):
        with self.locks.chat:
            user = self.room.get_user_or_raise(name)
        self.mediator.add_user_to_group('dj', user)

    def remove_dj(self, message: TextMessage, spec: CommandSpec, name: str):
        with self.locks.groups:
            self.mediator.profile.groups_manager.remove_user('dj', name)

    def add_to_whitelist(self, message: TextMessage, spec: CommandSpec, name: str):
        with self.locks.whitelist:
            self.mediator.profile.add_to_whitelist(name)

    def remove_from_whitelist(self, message: TextMessage, spec: CommandSpec, name: str):
        with self.locks.whitelist:
            self.mediator.profile.remove_from_whitelist(name)

    @ctx.require_host
    def whitelist(self, message: TextMessage, spec: CommandSpec):
        status = self.mediator.switch_whitelist_status()
        self.mediator.send_message(f'Whitelist {"on" if status else "off"}', user=self.mediator.to_user(message))

    def whitelist_status(self, message: TextMessage, spec: CommandSpec):
        self.mediator.send_message(
            f'Whitelist {"on" if self.mediator.whitelist_status else "off"}', user=self.mediator.to_user(message))

    def block_commands(self, message: TextMessage, spec: CommandSpec,
                       name: str, reason: Optional[str] = None):
        with self.locks.chat:
            user = self.room.get_user_or_raise(name)
            if self.mediator.is_admin_user(user) or self.mediator.is_bot_user(user):
                return
        with self.locks.blacklist:
            self.profile.add_to_blacklist(name, reason=reason, permanent=False)

    @ctx.require_host
    def kick(self, message: TextMessage, spec: CommandSpec, name: str, block_commands: bool = False):
        with self.locks.chat:
            user = self.room.get_user_or_raise(name)
            if self.mediator.is_admin_user(user) or self.mediator.is_bot_user(user):
                return
            self.room.kick(user)
        if block_commands:
            with self.locks.blacklist:
                self.profile.add_to_blacklist(name, permanent=False)

    @ctx.require_host
    def ban(self, message: TextMessage, spec: CommandSpec, name: str,
            reason: Optional[str] = None, permanent: bool = False):
        with self.locks.chat:
            user = self.room.get_user_or_raise(name)
            if self.mediator.is_admin_user(user) or self.mediator.is_bot_user(user):
                return
            self.room.ban(user)
        with self.locks.blacklist:
            self.profile.add_to_blacklist(name, reason=reason, permanent=permanent)

    def unban(self, message: TextMessage, spec: CommandSpec, name: str, full: bool = False):
        with self.locks.blacklist:
            self.profile.remove_from_blacklist(name, full)

    def dj_mode(self, message: TextMessage, spec: CommandSpec):
        with self.locks.dj_state:
            dj_state = self.context.states.switch('dj')
        self.mediator.send_message(f'DJ mode {"on" if dj_state else "off"}')

    def queue(self, message: TextMessage, spec: CommandSpec, page: str = '1'):
        vpage = validate_index(page, error_msg='Invalid page value')
        with self.locks.player:
            queue = self.player.queue.copy()
        if queue:
            self.mediator.send_message(queue_message(queue, vpage), user=self.mediator.to_user(message))
        else:
            self.mediator.send_message('Queue is empty', user=self.mediator.to_user(message))

    def search_results(self, message: TextMessage, spec: CommandSpec):
        with self.locks.search:
            search_list = self.search_list
        if search_list:
            self.mediator.send_message(search_message(search_list), user=self.mediator.to_user(message))
        else:
            self.mediator.send_message('Nothing was searched yet', user=self.mediator.to_user(message))

    def add_track(self, track: Track, force: bool = False, index: Optional[str] = None, **flags):
        with self.locks.player:
            vindex = None
            if index is not None:
                vindex = validate_index(index, error_msg='Invalid index value')
            if force:
                self.player.add_track(track, index=0, **flags)
                self.player.reset_timestamp()
            else:
                self.player.add_track(track, index=vindex, **flags)

    @ctx.dj_mode
    @ctx.require_player
    def play(self, message: TextMessage, spec: CommandSpec, url: str, **flags):
        self.mediator.send_message('Extracting track...', user=self.mediator.to_user(message))
        track = self.extractor.extract(url)
        self.add_track(track, **flags)

    @ctx.dj_mode
    @ctx.require_player
    def search(self, message: TextMessage, spec: CommandSpec, *values):
        self.mediator.send_message('Searching...', user=self.mediator.to_user(message))
        with self.locks.search:
            self.search_list = self.extractor.search(' '.join(values))
            formatted = search_message(self.search_list)
        self.mediator.send_message(formatted, user=self.mediator.to_user(message))

    @ctx.dj_mode
    @ctx.require_player
    def choose(self, message: TextMessage, spec: CommandSpec, number: str = '1', **flags):
        if not self.search_list:
            raise CommandException('No search results')
        vnumber = validate_index(number, max_index=3, error_msg='Invalid number value')
        with self.locks.search:
            info = self.search_list[vnumber-1]
            self.search_list = []
        self.add_track(info, **flags)

    @ctx.dj_mode
    def repeat(self, message: TextMessage, spec: CommandSpec):
        with self.locks.player:
            self.player.repeat ^= True
            repeat = self.player.repeat
        self.mediator.send_message(f'Repeat {"on" if repeat else "off"}', user=self.mediator.to_user(message))

    @ctx.dj_mode
    def next(self, message: TextMessage, spec: CommandSpec):
        with self.locks.player:
            self.player.reset_timestamp()
        self.mediator.send_message('Skipping current track', user=self.mediator.to_user(message))

    @ctx.dj_mode
    def remove_song(self, message: TextMessage, spec: CommandSpec, index: str = '1'):
        vindex = validate_index(index, error_msg='Invalid index value')
        with self.locks.player:
            self.player.pop_track(vindex-1)
        self.mediator.send_message('Track removed', user=self.mediator.to_user(message))

    @ctx.dj_mode
    def clear_queue(self, message: TextMessage, spec: CommandSpec):
        with self.locks.player:
            self.player.clear_queue()
        self.mediator.send_message('Queue cleared', user=self.mediator.to_user(message))

    @ctx.dj_mode
    def pause(self, message: TextMessage, spec: CommandSpec):
        with self.locks.player:
            self.player.pause()
        self.mediator.send_message('Player paused', user=self.mediator.to_user(message))

    @ctx.dj_mode
    def unpause(self, message: TextMessage, spec: CommandSpec):
        with self.locks.player:
            self.player.unpause()
        self.mediator.send_message('Player unpaused', user=self.mediator.to_user(message))
