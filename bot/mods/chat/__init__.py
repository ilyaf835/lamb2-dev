from __future__ import annotations
from typing import TYPE_CHECKING, Type, Optional

import re

from .api import AsyncChatAPI, ChatAPI, check_response_json
from .messages import AnyMessage, BaseMessage, TextMessage, JoinMessage, MusicMessage
from .exceptions import (
    ChatNotConnectedError,
    ChatAlreadyConnectedError,
    RoomNotConnectedError,
    RoomAlreadyConnectedError,
    InvalidRoomUrlError,
    UserNotFoundError
)

if TYPE_CHECKING:
    from collections.abc import Callable


ROOM_URL_PATTERN = re.compile(r'(?:https?://)?drrr\.com/room/\?id=.{10}')


def validate_room_url(url: str):
    if ROOM_URL_PATTERN.fullmatch(url):
        return True
    return False


def connection_required(func: Callable):
    def wrapper(self, *args, **kwargs):
        self.raise_for_connection()
        return func(self, *args, **kwargs)
    return wrapper


class User:

    def __init__(self, info: dict[str, str]):
        self.info = info
        self.id = self.info['id']
        self.name = self.info['name']
        self.tripcode = self.info.get('tripcode', '')
        if not self.tripcode:
            self.tripcode = ''


class Room:

    message_types: dict[str, Type[BaseMessage]]
    users: dict[str, User]

    def __init__(self, sync_api: ChatAPI, async_api: AsyncChatAPI):
        self.sync_api = sync_api
        self.async_api = async_api
        self.message_types = {
            'message': TextMessage,
            'music': MusicMessage,
            'join': JoinMessage
        }
        self.update_time = 0
        self.connected = False
        self.url = None
        self.dj_mode = False
        self.music = False
        self.host = None
        self.users = {}

    def raise_for_connection(self):
        if not self.connected:
            raise RoomNotConnectedError()

    @connection_required
    def is_host(self, user: User):
        if self.host:
            return self.host.name == user.name and self.host.tripcode == user.tripcode

    def reset(self):
        self.update_time = 0
        self.connected = True
        self.url = None
        self.dj_mode = False
        self.music = False
        self.host = None
        self.users = {}

    def join(self, room_url: str):
        if self.connected:
            raise RoomAlreadyConnectedError()
        if not validate_room_url(room_url):
            raise InvalidRoomUrlError()

        response = self.sync_api.join_room(room_url)
        response_json = check_response_json(response)
        self.reset()
        self.url = room_url

        return response_json

    async def async_join(self, room_url: str):
        if self.connected:
            raise RoomAlreadyConnectedError()
        if not validate_room_url(room_url):
            raise InvalidRoomUrlError()

        response = await self.async_api.join_room(room_url)
        response_json = check_response_json(response)
        self.reset()
        self.url = room_url

        return response_json

    @connection_required
    def leave(self):
        self.connected = False
        return self.sync_api.leave_room()

    @connection_required
    async def async_leave(self):
        self.connected = False
        return await self.async_api.leave_room()

    def update_users(self, users_list: list, host_id: str):
        for user_json in users_list:
            name = user_json['name']
            if name not in self.users:
                user = self.users[name] = User(user_json)
            else:
                user = self.users[name]
            if user.id == host_id:
                self.host = user

    def remove_users(self, users_list: list):
        user_names = {user_json['name'] for user_json in users_list}
        for name in self.users.copy():
            if name not in user_names:
                self.users.pop(name)

    def process_messages(self, messages_list: list) -> list[AnyMessage]:
        messages = []
        for message_json in messages_list:
            message_type = self.message_types.get(message_json['type'])
            if not message_type:
                continue
            messages.append(message_type(message_json, self.users))

        return messages

    def update_room(self, room_json: dict):
        users = room_json.get('users')
        if users:
            self.update_users(users, room_json['host'])

        messages = room_json.get('talks')
        if self.update_time and messages:
            messages = self.process_messages(messages)
        else:
            messages = []

        if users:
            self.remove_users(users)

        self.dj_mode = room_json.get('djMode', False)
        self.music = room_json['music']
        self.update_time = room_json['update']

        return messages

    @connection_required
    def get_update(self):
        response = self.sync_api.update_room(self.update_time)
        return check_response_json(response)

    @connection_required
    async def async_get_update(self):
        response = await self.async_api.update_room(self.update_time)
        return check_response_json(response)

    @connection_required
    def get_user(self, name: str):
        return self.users.get(name)

    @connection_required
    def get_user_or_raise(self, name: str):
        try:
            return self.users[name]
        except KeyError:
            raise UserNotFoundError(format_args=(name,))

    @connection_required
    def give_host(self, user: User):
        response = self.sync_api.give_host(user.id)
        self.host = user

        return response

    @connection_required
    async def async_give_host(self, user: User):
        response = await self.async_api.give_host(user.id)
        self.host = user

        return response

    @connection_required
    def kick(self, user: User):
        response = self.sync_api.kick(user.id)
        self.users.pop(user.name)

        return response

    @connection_required
    async def async_kick(self, user: User):
        response = await self.async_api.kick(user.id)
        self.users.pop(user.name)

        return response

    @connection_required
    def ban(self, user: User):
        response = self.sync_api.ban(user.id)
        self.users.pop(user.name)

        return response

    @connection_required
    async def async_ban(self, user: User):
        response = await self.async_api.ban(user.id)
        self.users.pop(user.name)

        return response

    @connection_required
    def launch_player(self, title: str, url: str):
        return self.sync_api.launch_player(title, url)

    @connection_required
    async def async_launch_player(self, title: str, url: str):
        return await self.async_api.launch_player(title, url)

    @connection_required
    def send_message(self, text: str, user: Optional[User] = None, url: Optional[str] = None):
        return self.sync_api.send_message(text, user_id=user.id if user else None, url=url)

    @connection_required
    async def async_send_message(self, text: str, user: Optional[User] = None, url: Optional[str] = None):
        return await self.async_api.send_message(text, user_id=user.id if user else None, url=url)


class Chat:

    def __init__(self, timeout: Optional[float] = 30):
        self.sync_api = ChatAPI(timeout=timeout)
        self.async_api = AsyncChatAPI(timeout=timeout)
        self.room = Room(self.sync_api, self.async_api)
        self.connected = False

    def raise_for_connection(self):
        if not self.connected:
            raise ChatNotConnectedError()

    @property
    def session_cookie(self):
        return self.sync_api.client.cookies['drrr-session-1']

    def login(self, name: str, passcode: str = '', icon: str = 'kyo-2x'):
        if self.connected:
            raise ChatAlreadyConnectedError()

        response = self.sync_api.login(f'{name}#{passcode}', icon=icon)
        response_json = check_response_json(response)
        self.async_api.client.cookies.update(self.sync_api.client.cookies)
        self.connected = True

        return response_json

    async def async_login(self, name: str, passcode: str = '', icon: str = 'kyo-2x'):
        if self.connected:
            raise ChatAlreadyConnectedError()

        response = await self.async_api.login(f'{name}#{passcode}', icon=icon)
        response_json = check_response_json(response)
        self.sync_api.client.cookies.update(self.async_api.client.cookies)
        self.connected = True

        return response_json

    @connection_required
    def logout(self):
        self.connected = False
        response = self.sync_api.logout()
        response_json = check_response_json(response)

        return response_json

    @connection_required
    async def async_logout(self):
        self.connected = False
        response = await self.async_api.logout()
        response_json = check_response_json(response)

        return response_json

    @connection_required
    def get_lounge_json(self):
        response = self.sync_api.get_lounge()
        response_json = check_response_json(response)

        return response_json

    @connection_required
    async def async_get_lounge_json(self):
        response = await self.async_api.get_lounge()
        response_json = check_response_json(response)

        return response_json

    @connection_required
    def join_room(self, room_url: str):
        return self.room.join(room_url)

    @connection_required
    async def async_join_room(self, room_url: str):
        return await self.room.async_join(room_url)

    @connection_required
    def leave_room(self):
        return self.room.leave()

    @connection_required
    async def async_leave_room(self):
        return await self.room.async_leave()
