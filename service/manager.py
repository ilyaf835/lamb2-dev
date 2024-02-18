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

    def create(self, session_id: str, session: dict[str, Any]):
        bot = Bot(session, self.extractor_address)
        try:
            bot.login()
            bot.join_room(session['room']['url'])
            bot.start()
        except ChatApiError as error:
            signal = pickle.dumps(('failed', session, session_id, error.msg))
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

    def __init__(self, server_address: tuple[str, int], extractor_address: tuple[str, int]):
        self.server_address = server_address
        self.extractor_address = extractor_address
        self.disconnects = deque()
        self.bots = {}
        self.running = False

        self.bots_event = threading.Event()
        self.connection_lock = threading.RLock()
        self.connection = ConnectionHandler(socket.create_connection(server_address))
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.connection.sock, selectors.EVENT_READ)

        self.commands_workers = ThreadsHandler(workers_count=4, start=True)
        self.commands = ManagerCommands(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.commands_workers.stop()
        self.selector.close()
        self.connection.close()
        for session_id, (bot, session) in yield_from(self.bots):
            self.bots.pop(session_id)
            self.shutdown_bot(bot, leave=True)

    def shutdown_bot(self, bot: Bot, leave: bool = False):
        try:
            if leave:
                bot.return_host()
                bot.leave_room()
            bot.logout()
        except Exception:
            pass
        finally:
            bot.extractor.close()
            bot.shutdown()

    def report_disconnected(self):
        while self.running:
            while self.disconnects:
                session_id, (bot, session), leave = self.disconnects.popleft()
                self.shutdown_bot(bot, leave=leave)
                signal = pickle.dumps(('disconnected', session, session_id, None))
                with self.connection_lock:
                    self.connection.send(signal)
            time.sleep(0.5)

    def update_sessions(self):
        while self.running:
            for session_id, (bot, session) in yield_from(self.bots):
                signal = pickle.dumps(('update', session, session_id, None))
                with self.connection_lock:
                    self.connection.send(signal)
            time.sleep(5)

    def receive_commands(self):
        while self.running:
            ready = self.selector.select(timeout=1)
            if ready:
                with self.connection_lock:
                    data = self.connection.recv()
                command, args = pickle.loads(data)
                if command == 'stop':
                    self.running = False
                    self.bots_event.set()
                else:
                    self.commands_workers.enqueue(getattr(self.commands, command), args=args)

    def run_bots(self):
        if not self.bots:
            self.bots_event.clear()
            self.bots_event.wait()
            if not self.running:
                return
        for session_id, (bot, session) in yield_from(self.bots):
            try:
                bot.run_once()
                if not bot.running:
                    self.disconnects.append((session_id, self.bots.pop(session_id), False))
            except Exception:
                self.disconnects.append((session_id, self.bots.pop(session_id), True))

    def run(self):
        self.running = True
        threading.Thread(target=self.receive_commands).start()
        threading.Thread(target=self.report_disconnected).start()
        threading.Thread(target=self.update_sessions).start()
        try:
            while self.running:
                self.run_bots()
        finally:
            self.running = False


class SigtermException(SystemExit):
    pass


def sigterm_callback(*args):
    raise SigtermException(128 + signal.SIGTERM)


def start_bot_manager(server_address: tuple[str, int], extractor_address: tuple[str, int]):
    signal.signal(signal.SIGTERM, sigterm_callback)
    with BotsManager(server_address, extractor_address) as manager:
        manager.run()
