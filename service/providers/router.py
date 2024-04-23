from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, Optional

import uuid
import asyncio
import aio_pika
from aio_pika import Message
from aio_pika.exceptions import DeliveryError
from pamqp.commands import Basic

from ..errors import Errors

if TYPE_CHECKING:
    from asyncio import Future
    from aio_pika.abc import AbstractChannel, AbstractExchange, AbstractIncomingMessage
    from aio_pika.message import ReturnedMessage
    from redis.asyncio import Redis


class RPC:

    futures: dict[str, tuple[Future, Callable[[Future[str], AbstractIncomingMessage], Any]]]

    def __init__(self, channel: AbstractChannel, exchange: AbstractExchange):
        self.channel = channel
        self.exchange = exchange
        self.futures = {}

    async def init(self):
        self.queue = await self.channel.declare_queue(exclusive=True)
        await self.queue.bind(self.exchange)

        self.channel.close_callbacks.add(self.on_close)
        self.channel.return_callbacks.add(self.on_message_return)
        await self.queue.consume(self.on_reply, no_ack=True)

    async def on_close(self, channel: AbstractChannel, exc: Optional[BaseException] = None):
        for future, callback in self.futures.values():
            if not future.done():
                future.set_exception(exc or asyncio.CancelledError)
        self.futures.clear()

    async def on_message_return(self, channel: AbstractChannel, message: ReturnedMessage):
        if message.correlation_id in self.futures:
            future, callback = self.futures.pop(message.correlation_id)
            if not future.done():
                future.set_exception(asyncio.CancelledError)

    async def on_reply(self, message: AbstractIncomingMessage):
        if message.correlation_id in self.futures:
            future, callback = self.futures.pop(message.correlation_id)
            await callback(future, message)

    def create_future(self, callback: Callable[[Future[str], AbstractIncomingMessage], Any]) -> tuple[Future[str], str]:
        correlation_id = str(uuid.uuid4())
        future: asyncio.Future[str] = asyncio.Future()
        self.futures[correlation_id] = (future, callback)
        future.add_done_callback(lambda future: self.futures.pop(correlation_id, None))

        return future, correlation_id


class RouterCommands:

    def __init__(self, router: Router):
        self.router = router
        self.redis = router.redis
        self.exchange = router.exchange
        self.lock = asyncio.Lock()

    async def create(self, session_id: str):
        async with self.lock:
            queue_name = await self.redis.get(f'balancers:{session_id}')
            if queue_name:
                return Errors.ALREADY_CREATED

            response = await self.redis.zrange('balancers:queue', 0, 0, desc=True, withscores=True)
            if not response:
                return Errors.NO_BALANCERS

            queue_name, workers_count = response[0]
            if workers_count <= 0:
                return Errors.NO_WORKERS

            await self.redis.set(f'balancers:{session_id}', queue_name)
            await self.redis.zincrby('balancers:queue', -1, queue_name)

        future = await self.router.publish_message(f'create/{session_id}'.encode(), queue_name)
        error = await future
        if error:
            async with self.lock:
                await self.redis.getdel(f'balancers:{session_id}')
                await self.redis.zincrby('balancers:queue', 1, queue_name)

            return error

    async def delete(self, session_id: str):
        async with self.lock:
            queue_name = await self.redis.getdel(f'balancers:{session_id}')
            if queue_name:
                await self.redis.zincrby('balancers:queue', 1, queue_name)
            else:
                return Errors.NO_BOT

        future = await self.router.publish_message(f'delete/{session_id}'.encode(), queue_name)
        return await future


class Router:

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def init(self, prefetch_count: int = 0, **kwargs):
        self.connection = await aio_pika.connect(**kwargs)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=prefetch_count)

        self.exchange = await self.channel.declare_exchange('balancers')
        self.rpc = RPC(self.channel, self.exchange)
        await self.rpc.init()

        self.commands = RouterCommands(self)

    async def close(self):
        await self.channel.close()
        await self.connection.close()

    async def command_callback(self, future: Future[str], message: AbstractIncomingMessage):
        future.set_result(message.body.decode())

    async def publish_message(self, message: bytes, queue_name: str):
        future, correlation_id = self.rpc.create_future(self.command_callback)
        try:
            confirm = await self.exchange.publish(
                Message(message, correlation_id=correlation_id, reply_to=self.rpc.queue.name), queue_name)
        except DeliveryError:
            future.cancel()
        else:
            if not isinstance(confirm, Basic.Ack):
                future.cancel()

        return future

    async def publish_command(self, command: str, session_id: str) -> str:
        command_func = getattr(self.commands, command, None)
        if not command_func:
            return Errors.NO_COMMAND
        try:
            return await command_func(session_id)
        except asyncio.CancelledError:
            return Errors.PUBLISH_ERROR
