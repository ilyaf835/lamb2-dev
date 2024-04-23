from __future__ import annotations
from typing import TYPE_CHECKING, Type

import pickle
import multiprocessing

from lamb.utils.threads import ThreadsHandler
from lamb.utils.sockets import SocketServer, BaseRequestHandler
from lamb.utils.pools import BasePool

if TYPE_CHECKING:
    from lamb.utils.sockets import ConnectionHandler
    from bot.mods.music.extractors.youtube import YoutubeExtractor


def start_extractor_server(sentinel_address: tuple[str, int], extractors_count: int):
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
    server.set_request_handler(ExtractorRequestHandler(server, YoutubeExtractor, extractors_count))
    conn = ConnectionHandler(socket.create_connection(sentinel_address))
    with conn:
        conn.send(pickle.dumps(server.address))
    with server:
        server.run(poll_interval=10)


def connect_extractor_server(extractors_count: int):
    sentinel = SocketServer(('127.0.0.1', 0))
    process = multiprocessing.Process(
        target=start_extractor_server, args=(sentinel.address, extractors_count), daemon=True)
    process.start()
    with sentinel:
        with sentinel.accept() as conn:
            extractor_address = pickle.loads(conn.recv())

    return process, extractor_address


class ExtractorsPool(BasePool):

    def __init__(self, count: int, extractor_cls: Type[YoutubeExtractor]):
        super().__init__(count)
        self.queue.extend(extractor_cls() for i in range(count))


class ExtractorRequestHandler(BaseRequestHandler):

    def __init__(self, server: SocketServer, extractor_cls: Type[YoutubeExtractor], extractors_count: int):
        self.server = server
        self.pool = ExtractorsPool(extractors_count, extractor_cls)
        self.workers = ThreadsHandler(workers_count=extractors_count, start=True)

    def execute_command(self, conn: ConnectionHandler, command: str, text: str):
        try:
            with self.pool.get_item() as extractor:
                if command == 'extract':
                    info = extractor.extract(text)
                    conn.send(pickle.dumps((info, None)))
                elif command == 'search':
                    info_list = extractor.search(text)
                    conn.send(pickle.dumps((info_list, None)))
        except Exception as error:
            conn.send(pickle.dumps((None, error)))
        except BaseException as error:
            conn.send(pickle.dumps((None, error)))
            raise

    def handle(self, conn: ConnectionHandler, data: bytes):
        command, text = pickle.loads(data)
        if command == 'shutdown':
            conn.close()
            self.server.shutdown()
        else:
            self.workers.enqueue(self.execute_command, args=(conn, command, text))
