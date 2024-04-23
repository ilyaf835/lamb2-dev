import asyncpg

from lamb.utils.cryptography import hash_passcode

from ..models import User, Bot


class PostgresProvider:

    async def init(self, **kwargs):
        self.pool = asyncpg.create_pool(**kwargs)
        await self.pool._async__init__()

    async def close(self):
        await self.pool.close()

    async def get_or_create_user(self, name: str, tripcode: str, passcode: str):
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("""
                SELECT id, name, tripcode FROM users
                WHERE name = $1 AND tripcode = $2
                """, name, tripcode)
            if not user:
                hashed_passcode, salt = hash_passcode(passcode)
                user = await conn.fetchrow("""
                    INSERT INTO users (name, tripcode, passcode, salt)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, name, tripcode
                    """, name, tripcode, hashed_passcode, salt)

        return User(user)  # type: ignore

    async def get_or_create_bot(self, name: str, passcode: str, user_id: str):
        async with self.pool.acquire() as conn:
            bot = await conn.fetchrow("""
                WITH ins AS(
                    INSERT INTO bots (name, passcode, user_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id) DO UPDATE
                        SET name = $1, passcode = $2
                    RETURNING name, tripcode, passcode, icon, language, command_prefix, whitelist, blacklist, groups, user_id
                )
                SELECT name, tripcode, passcode, icon, language, command_prefix, whitelist, blacklist, groups, user_id FROM ins
                UNION
                SELECT name, tripcode, passcode, icon, language, command_prefix, whitelist, blacklist, groups, user_id FROM bots
                WHERE user_id = $3
                """, name, passcode, user_id)

        return Bot(bot)  # type: ignore
