from __future__ import annotations
from typing import TYPE_CHECKING, Any

import datetime
import json
import pickle
import signal
import socket
import asyncio
import threading
import multiprocessing
from heapq import heapify
from collections import deque

import asyncpg
import aio_pika
import redis.asyncio as redis

from lamb.utils.locks import AsyncLocksProxy
from lamb.utils.sockets import SocketServer, ConnectionHandler, BaseRequestHandler

from .manager import start_bot_manager
from .bot.extractor import connect_extractor_server

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop, Future
    from aio_pika.abc import AbstractIncomingMessage


async def write_session(conn, whitelist, blacklist, groups, user_id, **kwargs):
    return await conn.execute("""
        UPDATE bots SET whitelist = $1, blacklist = $2, groups = $3
        WHERE user_id = $4
        """, json.dumps(whitelist), json.dumps(blacklist), json.dumps(groups), user_id)


class Worker:

    def __init__(self, server: SocketServer, extractor_address: tuple[str, int]):
        self.server = server
        self.extractor_address = extractor_address
        self.running_instances = 0

    def __lt__(self, other: Any):
        return self.running_instances < other.running_instances

    def start(self):
        self.process = multiprocessing.Process(
            target=start_bot_manager, args=(self.server.address, self.extractor_address), daemon=True)
        self.process.start()
        self.connection = self.server.accept()

    def stop(self):
        self.running_instances = 0
        self.connection.send(pickle.dumps(('stop', None)))

    def create_instance(self, session_id: str, session: dict[str, Any]):
        self.running_instances += 1
        self.connection.send(pickle.dumps(('create', (session_id, session))))

    def delete_instance(self, session_id: str):
        self.running_instances -= 1
        self.connection.send(pickle.dumps(('delete', (session_id,))))


class BalancerRequestHandler(BaseRequestHandler):

    def __init__(self, balancer: LoadBalancer):
        self.balancer = balancer
        self.signals_queue = balancer.signals_queue

    def handle(self, conn: ConnectionHandler, data: bytes):
        self.signals_queue.append((conn, pickle.loads(data)))


class BalancerCommands:

    def __init__(self, balancer: LoadBalancer):
        self.balancer = balancer
        self.workers = balancer.workers
        self.sessions = balancer.sessions
        self.messages = balancer.messages
        self.redis = balancer.redis

    async def create(self, message: AbstractIncomingMessage, session_id: str):
        session = await self.redis.json().get(f'session:{session_id}')
        heapify(self.workers)
        self.messages[session_id] = message
        self.workers[0].create_instance(session_id, session)

    async def delete(self, message: AbstractIncomingMessage, session_id: str):
        worker = self.sessions.pop(session_id, None)
        if worker:
            self.messages[session_id] = message
            worker.delete_instance(session_id)
        else:
            await self.balancer.send_reply(message, b'')


class BalancerSignals:

    def __init__(self, balancer: LoadBalancer):
        self.balancer = balancer
        self.sessions = balancer.sessions
        self.messages = balancer.messages
        self.connections = balancer.connections
        self.balancer_queue = balancer.balancer_queue
        self.redis = balancer.redis

    async def connected(self, conn: ConnectionHandler, session: dict[str, Any],
                        session_id: str, error: str):
        self.sessions[session_id] = self.connections[conn]
        await self.redis.expire(f'session:{session_id}', self.balancer.SESSION_TTL)
        await self.balancer.send_reply(self.messages.pop(session_id), b'')

    async def failed(self, conn: ConnectionHandler, session: dict[str, Any],
                     session_id: str, error: str):
        self.connections[conn].running_instances -= 1
        await self.balancer.send_reply(self.messages.pop(session_id), error.encode())

    async def deleted(self, conn: ConnectionHandler, session: dict[str, Any],
                      session_id: str, error: str):
        if not error:
            await self.balancer.write_session(**session['bot'])
            await self.redis.json().delete(f'session:{session_id}', path='$')
        await self.balancer.send_reply(self.messages.pop(session_id), b'')

    async def disconnected(self, conn: ConnectionHandler, session: dict[str, Any],
                           session_id: str, error: str):
        worker = self.sessions.pop(session_id, None)
        if worker:
            worker.running_instances -= 1
        await self.redis.delete(f'balancers:{session_id}')
        await self.redis.zincrby('balancers:queue', 1, self.balancer_queue.name)
        await self.balancer.write_session(**session['bot'])
        await self.redis.json().delete(f'session:{session_id}', path='$')

    async def update(self, conn: ConnectionHandler, session: dict[str, Any],
                     session_id: str, error: str):
        await self.redis.expire(f'session:{session_id}', self.balancer.SESSION_TTL)
        await self.redis.json().set(f'session:{session_id}', '$.bot', session['bot'])
        await self.balancer.write_session(**session['bot'])


class LoadBalancer:

    workers: list[Worker]
    connections: dict[ConnectionHandler, Worker]
    sessions: dict[str, Worker]
    messages: dict[str, AbstractIncomingMessage]
    signals_queue: deque[tuple[ConnectionHandler, tuple[str, Any]]]

    def __init__(self, server_address: tuple[str, int], extractor_address: tuple[str, int],
                 workers_count: int, instances_count: int):
        self.server_address = server_address
        self.extractor_address = extractor_address
        self.workers_count = workers_count
        self.instances_count = instances_count
        self.capacity = workers_count * instances_count

        self.workers = []
        self.connections = {}
        self.sessions = {}
        self.messages = {}
        self.signals_queue = deque()
        self.locks = AsyncLocksProxy()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        for worker in self.workers:
            worker.stop()
        self.server.stop()
        await self.finalize()
        await self.broker_channel.close()
        await self.broker_connection.close()
        await self.redis.close()
        await self.postgres_pool.close()
        for worker in self.workers:
            worker.process.join()

    async def finalize(self):
        await self.redis.zrem('balancers:queue', self.balancer_queue.name)
        for session_id in self.sessions:
            bot = await self.redis.json().get(f'session:{session_id}', '$.bot')
            await self.write_session(**bot[0])
        for session_id in self.sessions:
            await self.redis.delete(f'balancers:{session_id}')
            await self.redis.json().delete(f'session:{session_id}')

    async def setup_postgres(self, **kwargs):
        self.postgres_pool = asyncpg.create_pool(**kwargs)
        await self.postgres_pool._async__init__()

    async def setup_rabbitmq(self, prefetch_count: int = 0, **kwargs):
        self.broker_connection = await aio_pika.connect(**kwargs)
        self.broker_channel = await self.broker_connection.channel()
        await self.broker_channel.set_qos(prefetch_count=prefetch_count)

        self.balancers_exchange = await self.broker_channel.declare_exchange('balancers')
        self.balancer_queue = await self.broker_channel.declare_queue(exclusive=True)
        await self.balancer_queue.bind(self.balancers_exchange)

    async def setup_redis(self, **kwargs):
        self.redis = redis.Redis(**kwargs)
        await self.redis.zadd('balancers:queue', {self.balancer_queue.name: self.capacity})

    async def setup_commands(self):
        self.commands = BalancerCommands(self)

    async def setup_signals(self):
        self.signals = BalancerSignals(self)

    async def setup_server(self):
        self.server = SocketServer(self.server_address)
        self.server.set_request_handler(BalancerRequestHandler(self))

    async def setup_workers(self):
        for i in range(self.workers_count):
            worker = Worker(self.server, self.extractor_address)
            worker.start()
            self.connections[worker.connection] = worker
            self.workers.append(worker)

    async def setup(self, session_ttl: int | datetime.timedelta, rabbitmq_settings: dict[str, Any],
                    redis_settings: dict[str, Any], postgres_settings: dict[str, Any]):
        self.SESSION_TTL = session_ttl
        await self.setup_rabbitmq(**rabbitmq_settings)
        await self.setup_postgres(**postgres_settings)
        await self.setup_redis(**redis_settings)
        await self.setup_commands()
        await self.setup_signals()
        await self.setup_server()
        await self.setup_workers()

    async def write_session(self, **kwargs):
        async with self.postgres_pool.acquire() as conn:
            return await write_session(conn, **kwargs)

    async def send_reply(self, message: AbstractIncomingMessage, reply_message: bytes):
        if message.reply_to is None:
            return
        await self.balancers_exchange.publish(
            aio_pika.Message(reply_message, correlation_id=message.correlation_id), message.reply_to)
        await message.ack()

    async def process_message(self, message: AbstractIncomingMessage):
        command, session_id = message.body.decode().split('/')
        async with self.locks.get(session_id):
            await getattr(self.commands, command)(message, session_id)

    def run_server(self, future: Future, loop: AbstractEventLoop):
        try:
            while True:
                stop = self.server.run_once(timeout=10)
                if stop:
                    break
                while self.signals_queue:
                    conn, (signal, *args) = self.signals_queue.popleft()
                    if signal == b'crashed':
                        break
                    asyncio.run_coroutine_threadsafe(getattr(self.signals, signal)(conn, *args), loop)
        except BaseException as e:
            future.set_exception(e)
            raise
        finally:
            self.server.close()
            if not future.exception():
                future.set_result(None)

    async def run(self):
        future = asyncio.Future()
        loop = asyncio.get_event_loop()
        threading.Thread(target=self.run_server, args=(future, loop), daemon=True).start()
        await self.balancer_queue.consume(self.process_message)
        try:
            return await future
        except asyncio.CancelledError:
            pass


def parse_args():
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument('-w', '--workers', type=int, required=True)
    p.add_argument('-i', '--instances', type=int, required=True)
    p.add_argument('-p', '--port', type=int, default=0)
    args = vars(p.parse_args())

    return {'workers_count': args['workers'],
            'instances_count': args['instances'],
            'server_port': args['port']}


class SigtermException(SystemExit):
    pass


def sigterm_callback(*args):
    raise SigtermException(128 + signal.SIGTERM)


async def main(server_port: int, workers_count: int, instances_count: int, **settings):
    server_address = ('127.0.0.1', server_port)
    workers_count = max(workers_count, 1)
    instances_count = max(instances_count, 1)
    extractors_count = max((workers_count * instances_count) // 10, 1)

    signal.signal(signal.SIGTERM, sigterm_callback)
    extractor_process, extractor_address = connect_extractor_server(extractors_count)
    extractor_conn = ConnectionHandler(socket.create_connection(extractor_address))
    try:
        async with LoadBalancer(server_address, extractor_address, workers_count, instances_count) as lb:
            await lb.setup(**settings)
            await lb.run()
    finally:
        extractor_conn.send(pickle.dumps(('shutdown', None)))
        extractor_process.join()


def run():
    import os

    args = parse_args()
    settings = {
        'session_ttl': datetime.timedelta(minutes=1),
        'postgres_settings': {
            'host': os.environ['POSTGRES_HOST'],
            'user': os.environ['POSTGRES_USER'],
            'password': os.environ['POSTGRES_PASSWORD'],
            'database': os.environ['POSTGRES_DB']},
        'rabbitmq_settings': {
            'host': os.environ['RABBITMQ_HOST'],
            'prefetch_count': 100},
        'redis_settings': {
            'host': os.environ['REDIS_HOST'],
            'protocol': 3,
            'decode_responses': True}}

    asyncio.run(main(**args, **settings))
