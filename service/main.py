from __future__ import annotations

from .providers.chat import ChatProvider
from .providers.rd import RedisProvider
from .providers.postgres import PostgresProvider
from .providers.router import Router

from .config import Config
from .errors import Errors
from .validation import validate_create_command


class Service:

    async def init(self, config: Config = Config()):
        self.config = config
        self.chat = ChatProvider()
        self.redis = RedisProvider(**self.config.REDIS_SETTINGS)
        self.postgres = PostgresProvider()
        await self.postgres.init(**self.config.POSTGRES_SETTINGS)
        self.router = Router(self.redis.redis)
        await self.router.init(**self.config.RABBITMQ_SETTINGS)

    async def close(self):
        await self.chat.close()
        await self.redis.close()
        await self.postgres.close()
        await self.router.close()

    async def create_bot(self, session_id: str, user_name: str,
                         bot_name: str, room_url: str, hidden: bool):
        if await self.redis.check_session_exists(session_id):
            return Errors.ALREADY_CREATED

        command = validate_create_command(
            user_name, bot_name, room_url, hidden)
        user_tripcode, room_name = await self.chat.get_user_info(
            user_name, bot_name, command.room_id, hidden)

        user = await self.postgres.get_or_create_user(
            command.user_name, user_tripcode, command.user_passcode)
        bot = await self.postgres.get_or_create_bot(
            command.bot_name, command.bot_passcode, user['id'])

        await self.redis.create_session_json(
            session_id, self.config.SESSION_TTL, {
                'room': {'id': command.room_id, 'url': room_url, 'name': room_name},
                'user': user, 'bot': bot})

        error = await self.router.publish_command('create', session_id)
        if error:
            await self.redis.delete_session_json(session_id)
            return error

    async def delete_bot(self, session_id: str):
        if not await self.redis.check_session_exists(session_id):
            return Errors.NO_BOT

        error = await self.router.publish_command('delete', session_id)
        if error:
            return error
