from __future__ import annotations
from typing import TYPE_CHECKING, Any

import redis.asyncio as redis

if TYPE_CHECKING:
    from datetime import timedelta


class RedisProvider:

    def __init__(self, **kwargs):
        self.redis = redis.Redis(**kwargs)

    async def close(self):
        await self.redis.aclose()  # type: ignore

    async def check_session_exists(self, session_id: str):
        return bool(await self.redis.exists(f'session:{session_id}'))

    async def get_session_json(self, session_id: str, path: str = '$'):
        return await self.redis.json().get(f'session:{session_id}', path)

    async def create_session_json(self, session_id: str, ttl: int | timedelta, session: dict[str, Any]):
        await self.redis.json().set(f'session:{session_id}', '$', session)
        await self.redis.expire(f'session:{session_id}', ttl)

    async def update_session_json(self, session_id: str, data: dict[str, Any], path: str = '$'):
        return await self.redis.json().set(f'session:{session_id}', path, data)

    async def delete_session_json(self, session_id: str):
        return await self.redis.json().delete(f'session:{session_id}', path='$')

    async def set_session_ttl(self, session_id: str, ttl: int | timedelta):
        return await self.redis.expire(f'session:{session_id}', ttl)
