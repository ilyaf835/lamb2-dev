from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional

import json
import httpx

from .exceptions import ChatApiError, ChatHttpError

if TYPE_CHECKING:
    from collections.abc import Callable


def check_response_json(response: httpx.Response) -> dict[str, Any]:
    try:
        response_json = response.json()
    except json.JSONDecodeError:
        raise ChatApiError('Invalid response from chat API', response)
    else:
        response_error = response_json.get('error')
        if response_error:
            raise ChatApiError(response_error, response, response_json=response_json)

    return response_json


def async_catch_error(func: Callable):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception:
            raise ChatHttpError()

    return wrapper


def catch_error(func: Callable):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            raise ChatHttpError()

    return wrapper


class AsyncChatAPI:

    def __init__(self, timeout: Optional[float] = None):
        self.client = httpx.AsyncClient(timeout=timeout)
        self.client.headers.update({'User-Agent': 'Bot'})

    @async_catch_error
    async def login(self, name: str, icon: str = 'kyo-2x'):
        response = await self.client.get('https://drrr.com/?api=json')
        token = response.json().get('token')
        data = {
            'name': name,
            'token': token,
            'login': 'ENTER',
            'direct-join': '',
            'language': 'en-US',
            'icon': icon
        }
        return await self.client.post('https://drrr.com/?api=json', data=data)

    @async_catch_error
    async def logout(self):
        return await self.client.post('https://drrr.com/logout?api=json')

    @async_catch_error
    async def get_lounge(self):
        return await self.client.get('https://drrr.com/lounge/?api=json')

    @async_catch_error
    async def join_room(self, url: str):
        return await self.client.get(f'{url}&api=json')

    @async_catch_error
    async def update_room(self, update_time: float, fast: bool = False):
        return await self.client.get(f'https://drrr.com/json.php?{"fast=1&" if fast else ""}update={update_time}')

    @async_catch_error
    async def leave_room(self):
        return await self.client.post('https://drrr.com/room/?ajax=1&api=json', data={'leave': 'leave'})

    @async_catch_error
    async def give_host(self, user_id: str):
        return await self.client.post('https://drrr.com/room/?ajax=1&api=json', data={'new_host': user_id})

    @async_catch_error
    async def kick(self, user_id: str):
        return await self.client.post('https://drrr.com/room/?ajax=1&api=json', data={'kick': user_id})

    @async_catch_error
    async def ban(self, user_id: str):
        return await self.client.post('https://drrr.com/room/?ajax=1&api=json', data={'ban': user_id})

    @async_catch_error
    async def launch_player(self, title: str, url: str):
        return await self.client.post(
            'https://drrr.com/room/?ajax=1&api=json', data={'music': 'music', 'name': title, 'url': url})

    @async_catch_error
    async def send_message(self, text: str, user_id: Optional[str] = None, url: Optional[str] = None):
        return await self.client.post(
            'https://drrr.com/room/?ajax=1&api=json', data={'message': text, 'to': user_id, 'url': url})


class ChatAPI:

    def __init__(self, timeout: Optional[float] = None):
        self.client = httpx.Client(timeout=timeout)
        self.client.headers.update({'User-Agent': 'Bot'})

    @catch_error
    def login(self, name: str, icon: str = 'kyo-2x'):
        response = self.client.get('https://drrr.com/?api=json')
        token = response.json().get('token')
        data = {
            'name': name,
            'token': token,
            'login': 'ENTER',
            'direct-join': '',
            'language': 'en-US',
            'icon': icon
        }
        return self.client.post('https://drrr.com/?api=json', data=data)

    @catch_error
    def logout(self):
        return self.client.post('https://drrr.com/logout?api=json')

    @catch_error
    def get_lounge(self):
        return self.client.get('https://drrr.com/lounge/?api=json')

    @catch_error
    def join_room(self, url: str):
        return self.client.get(f'{url}&api=json')

    @catch_error
    def update_room(self, update_time: float, fast: bool = False):
        return self.client.get(f'https://drrr.com/json.php?{"fast=1&" if fast else ""}update={update_time}')

    @catch_error
    def leave_room(self):
        return self.client.post('https://drrr.com/room/?ajax=1&api=json', data={'leave': 'leave'})

    @catch_error
    def give_host(self, user_id: str):
        return self.client.post('https://drrr.com/room/?ajax=1&api=json', data={'new_host': user_id})

    @catch_error
    def kick(self, user_id: str):
        return self.client.post('https://drrr.com/room/?ajax=1&api=json', data={'kick': user_id})

    @catch_error
    def ban(self, user_id: str):
        return self.client.post('https://drrr.com/room/?ajax=1&api=json', data={'ban': user_id})

    @catch_error
    def launch_player(self, title: str, url: str):
        return self.client.post(
            'https://drrr.com/room/?ajax=1&api=json', data={'music': 'music', 'name': title, 'url': url})

    @catch_error
    def send_message(self, text: str, user_id: Optional[str] = None, url: Optional[str] = None):
        return self.client.post(
            'https://drrr.com/room/?ajax=1&api=json', data={'message': text, 'to': user_id, 'url': url})
