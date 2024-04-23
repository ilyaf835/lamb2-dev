from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional

import re
import asyncio

from bot.mods.chat import AsyncChatAPI
from bot.mods.chat.exceptions import ChatHttpError

from .exceptions import ChatRequestError, ChatApiNotResponding

if TYPE_CHECKING:
    from httpx import Response


ROOM_URL_PATTERN = re.compile(r'(?:https?://)?drrr\.com/room/\?id=(?P<id>.{10})')
ROOM_URL_BASE = 'drrr.com/room/?id='


def check_response_json(response: Response) -> dict[str, Any]:
    response_json = response.json()
    error = response_json.get('error')
    if error:
        raise ChatRequestError(error)

    return response_json


def get_user_room(rooms: list[dict[str, Any]], room_id: str):
    for room in rooms:
        if room['id'] == room_id:
            return room
    raise ChatRequestError('Room does not exists')


def check_room_info(room: dict[str, Any], user_name: str, user_tripcode: str, bot_name: str):
    if int(room['total']) == int(room['limit']):
        raise ChatRequestError('Room is full')
    if user_name != room['host']['name'] or user_tripcode != room['host'].get('tripcode'):
        raise ChatRequestError('User must be host of the room')
    for user in room['users']:
        if user['name'] == bot_name:
            raise ChatRequestError('User with the same nickname as bot is in room')


class ChatProvider:

    def __init__(self, timeout: Optional[float] = 30):
        self.api = AsyncChatAPI(timeout=timeout)

    async def close(self):
        await self.api.client.aclose()

    async def get_lounge_json(self, full_user_name: str):
        try:
            check_response_json(await self.api.login(full_user_name))
            lounge = check_response_json(await self.api.get_lounge())
            asyncio.create_task(self.api.logout())
            return lounge
        except ChatHttpError:
            raise ChatApiNotResponding()

    async def get_user_info(self, full_user_name: str, bot_name: str,
                            room_id: str, hidden: bool = False) -> tuple[str, str]:
        lounge = await self.get_lounge_json(full_user_name)
        profile = lounge['profile']
        room_name = '[hidden]'
        if not hidden:
            room = get_user_room(lounge['rooms'], room_id)
            check_room_info(room, profile['name'], profile['tripcode'], bot_name)
            room_name = room['name']

        return profile['tripcode'], room_name
