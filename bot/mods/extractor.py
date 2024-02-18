from __future__ import annotations

import pickle
import socket
import threading

from lamb.utils.sockets import ConnectionHandler

from .music import Track


class Extractor:

    def __init__(self, address: tuple[str, int]):
        self.address = address
        self.conn = ConnectionHandler(socket.create_connection(address))
        self.lock = threading.RLock()

    def close(self):
        self.conn.close()

    def extract(self, url: str):
        with self.lock:
            self.conn.send(pickle.dumps(('extract', url)))
            info, error = pickle.loads(self.conn.recv())
            if error:
                raise error

        return Track(**info)

    def search(self, text: str):
        with self.lock:
            self.conn.send(pickle.dumps(('search', text)))
            search_list, error = pickle.loads(self.conn.recv())
            if error:
                raise error

        return [Track(**info) for info in search_list]

    def shutdown(self):
        with self.lock:
            self.conn.send(pickle.dumps(('shutdown', None)))
        self.close()
