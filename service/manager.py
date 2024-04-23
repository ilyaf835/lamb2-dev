from __future__ import annotations
from typing import Any, TypeVar, Generator

import time
import pickle
import signal
import socket
import selectors
import threading
from collections import deque

from lamb.utils.sockets import ConnectionHandler
from lamb.utils.threads import ThreadsHandler

from bot.mods.chat.exceptions import ChatApiError

from .errors import Errors
from .bot import Bot
from .logging.logger import logger


T = TypeVar('T')


def yield_from(d: dict[str, T]) -> Generator[tuple[str, T], Any, None]:
    for key in d.copy():
        try:
            yield key, d[key]
        except KeyError:
            continue


class ManagerCommands:

    def __init__(self, manager: BotsManager):
        self.manager = manager
        self.extractor_address = manager.extractor_address
        self.bots_event = manager.bots_event
        self.connection_lock = manager.connection_lock
        self.connection = manager.connection
        self.bots = manager.bots
        self.sentinel_selector = manager.sentinel_selector

    def create(self, session_id: str, session: dict[str, Any]):
        bot = Bot(session, self.extractor_address, self.sentinel_selector, session_id)
        try:
            bot.login()
            bot.join_room(session['room']['url'])
        except ChatApiError as error:
            signal = pickle.dumps(('failed', session, session_id, error.msg))
        except Exception as e:
            logger.exception(e)
            signal = pickle.dumps(('failed', session, session_id, 'Internal service error'))
        else:
            signal = pickle.dumps(('connected', session, session_id, None))
            self.bots[session_id] = (bot, session)
            self.bots_event.set()
        with self.connection_lock:
            self.connection.send(signal)

    def delete(self, session_id: str):
        bot, session = self.bots.pop(session_id, (None, None))
        if bot:
            self.manager.shutdown_bot(bot, leave=True)
            signal = pickle.dumps(('deleted', session, session_id, None))
        else:
            signal = pickle.dumps(('deleted', None, session_id, Errors.NO_BOT))
        with self.connection_lock:
            self.connection.send(signal)


class BotsManager:

    disconnects: deque[tuple[str, tuple[Bot, dict[str, Any]], bool]]
    bots: dict[str, tuple[Bot, dict[str, Any]]]
    exceptions: list[BaseException]

    def __init__(self, server_address: tuple[str, int], extractor_address: tuple[str, int]):
        self.server_address = server_address
        self.extractor_address = extractor_address
        self.disconnects = deque()
        self.bots = {}
        self.exceptions = []
        self.running = False

        self.bots_event = threading.Event()
        self.connection_lock = threading.RLock()
        self.connection = ConnectionHandler(socket.create_connection(server_address))
        self.sentinel_selector = selectors.DefaultSelector()
        self.commands_selector = selectors.DefaultSelector()
        self.commands_selector.register(self.connection.sock, selectors.EVENT_READ)

        self.commands_workers = ThreadsHandler(workers_count=4, start=True)
        self.commands = ManagerCommands(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def exception_callback(self, exc: BaseException):
        self.exceptions.append(exc)

    def close(self):
        self.commands_workers.stop()
        self.connection.close()
        for session_id, (bot, session) in self.bots.items():
            self.shutdown_bot(bot, leave=True)
        self.bots.clear()
        self.commands_selector.close()

    def shutdown_bot(self, bot: Bot, leave: bool = False):
        try:
            if leave:
                bot.return_host()
                bot.leave_room()
        except Exception as e:
            logger.exception(e)
        finally:
            bot.shutdown()
            bot.extractor.close()

    def report_disconnected(self):
        while self.disconnects:
            session_id, (bot, session), leave = self.disconnects.popleft()
            self.shutdown_bot(bot, leave=leave)
            signal = pickle.dumps(('disconnected', session, session_id, None))
            with self.connection_lock:
                self.connection.send(signal)

    def update_sessions(self):
        for session_id, (bot, session) in yield_from(self.bots):
            signal = pickle.dumps(('update', session, session_id, None))
            with self.connection_lock:
                self.connection.send(signal)

    def send_signals(self):
        update_timestamp = 0.0
        while self.running:
            time.sleep(1)
            self.report_disconnected()
            if time.time() - update_timestamp > 5:
                self.update_sessions()
                update_timestamp = time.time()

    def receive_commands(self):
        while self.running:
            ready = self.commands_selector.select(timeout=0.5)
            if ready:
                with self.connection_lock:
                    data = self.connection.recv()
                command, args = pickle.loads(data)
                if command == 'stop':
                    self.running = False
                    self.bots_event.set()
                else:
                    self.commands_workers.enqueue(
                        getattr(self.commands, command), args=args,
                        exception_callbacks=[self.exception_callback])

    def run_bot_once(self, session_id: str, bot: Bot):
        try:
            bot.run_once(timeout=0)
            if not bot.running:
                self.disconnects.append((session_id, self.bots.pop(session_id), False))
        except Exception as e:
            logger.exception(e)
            self.disconnects.append((session_id, self.bots.pop(session_id), True))

    def run_bots(self):
        if not self.bots:
            self.bots_event.clear()
            self.bots_event.wait()
            if not self.running:
                return
        ready = self.sentinel_selector.select(timeout=0.1)
        if ready:
            for key, events in ready:
                session_id = key.data[0]
                bot, session = self.bots.get(session_id, (None, None))
                if bot:
                    self.run_bot_once(session_id, bot)
        for session_id, (bot, session) in yield_from(self.bots):
            self.run_bot_once(session_id, bot)

    def run(self):
        self.running = True
        threads_queue = ThreadsHandler(workers_count=2, start=True)
        threads_queue.enqueue(self.receive_commands, exception_callbacks=[self.exception_callback])
        threads_queue.enqueue(self.send_signals, exception_callbacks=[self.exception_callback])
        try:
            while self.running:
                if self.exceptions:
                    raise self.exceptions[0]
                self.run_bots()
        except:
            with self.connection_lock:
                self.connection.send(b'crashed')
            raise
        finally:
            self.running = False
            threads_queue.stop()


class SigtermException(SystemExit):
    pass


def sigterm_callback(*args):
    raise SigtermException(128 + signal.SIGTERM)


def start_bot_manager(server_address: tuple[str, int], extractor_address: tuple[str, int]):
    signal.signal(signal.SIGTERM, sigterm_callback)
    with BotsManager(server_address, extractor_address) as manager:
        manager.run()
