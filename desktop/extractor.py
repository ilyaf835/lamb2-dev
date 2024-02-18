from __future__ import annotations
from typing import TYPE_CHECKING, Type

import pickle
import multiprocessing

from lamb.utils.sockets import SocketServer, BaseRequestHandler

from bot.mods.music.extractors.exceptions import ExtractorException

if TYPE_CHECKING:
    from lamb.utils.sockets import ConnectionHandler
    from bot.mods.music.extractors.youtube import YoutubeExtractor


def start_extractor_server(sentinel_address: tuple[str, int]):
    import pickle
    import signal
    import socket
    from lamb.utils.sockets import SocketServer, ConnectionHandler
    from bot.mods.music.extractors.youtube import YoutubeExtractor

    class SigtermException(SystemExit):
        pass

    def sigterm_callback(*args):
        raise SigtermException(128 + signal.SIGTERM)

    signal.signal(signal.SIGTERM, sigterm_callback)
    server = SocketServer(('127.0.0.1', 0))
    server.set_request_handler(ExtractorRequestHandler(server, YoutubeExtractor))
    conn = ConnectionHandler(socket.create_connection(sentinel_address))
    with conn:
        conn.send(pickle.dumps(server.address))
    with server:
        server.run(poll_interval=10)


def connect_extractor_server():
    sentinel = SocketServer(('127.0.0.1', 0))
    process = multiprocessing.Process(target=start_extractor_server, args=(sentinel.address,), daemon=True)
    process.start()
    with sentinel:
        with sentinel.accept() as conn:
            extractor_address = pickle.loads(conn.recv())

    return process, extractor_address


class ExtractorRequestHandler(BaseRequestHandler):

    def __init__(self, server: SocketServer, extractor_cls: Type[YoutubeExtractor]):
        self.server = server
        self.extractor = extractor_cls()

    def execute_command(self, conn: ConnectionHandler, command: str, text: str):
        if command == 'shutdown':
            conn.close()
            self.server.shutdown()
        elif command == 'extract':
            info = self.extractor.extract(text)
            conn.send(pickle.dumps((info, None)))
        elif command == 'search':
            info_list = self.extractor.search(text)
            conn.send(pickle.dumps((info_list, None)))

    def handle(self, conn: ConnectionHandler, data: bytes):
        command, text = pickle.loads(data)
        try:
            self.execute_command(conn, command, text)
        except ExtractorException as error:
            conn.send(pickle.dumps((None, error)))
