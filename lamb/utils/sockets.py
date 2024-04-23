from __future__ import annotations
from typing import Optional

import os
import sys
import socket
import struct
import selectors
import logging

from lamb.utils.pools import BasePool


logger = logging.getLogger(__name__)


ACCEPT_CONN = 1
HANDLE_REQUEST = 2
SHUTDOWN_REQUEST = 3

SIGNAL_STOP = b'stop'
SIGNAL_SHUTDOWN = b'shutdown'


class BadPayloadHeader(ConnectionError):
    pass


class ConnectionClosed(ConnectionError):
    pass


def send(sock: socket.socket, data: bytes):
    size = len(data)
    payload = memoryview(struct.pack(f'!Q{size}s', size, data))
    fullsize = payload.nbytes
    sent = 0
    while sent < fullsize:
        chunk = sock.send(payload[sent:])
        sent += chunk


def recv(sock: socket.socket):
    header = sock.recv(8)
    if header == b'':
        raise ConnectionClosed(f'Connection from {sock.getpeername()} closed')
    if len(header) != 8:
        raise BadPayloadHeader('Bad payload header')

    buffer = bytearray()
    size, = struct.unpack('!Q', header)
    while size:
        chunk = sock.recv(min(size, 8192))
        if chunk == b'':
            raise ConnectionClosed(f'Connection from {sock.getpeername()} closed')
        buffer.extend(chunk)
        size -= len(chunk)

    return buffer


class ConnectionHandler:

    def __init__(self, sock: socket.socket):
        self.sock = sock

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        return self.sock.close()

    def send(self, data: bytes):
        return send(self.sock, data)

    def recv(self):
        return recv(self.sock)


class ConnectionsPool(BasePool):

    item: ConnectionHandler

    def __init__(self, count: int, address: tuple[str, int], lazy: bool = False):
        super().__init__(count)
        self.address = address
        if not lazy:
            self.queue.extend(ConnectionHandler(socket.create_connection(address)) for i in range(count))

    def close_connections(self):
        for conn in self.queue:
            conn.close()

    def get_item(self):
        if len(self.queue) < self.count:
            self.queue.append(ConnectionHandler(socket.create_connection(self.address)))
        return super().get_item()


class BaseRequestHandler:

    def handle(self, conn, data):
        pass


class SocketServer:

    def __init__(self, address: tuple[str, int], family=socket.AF_INET, backlog: Optional[int] = None,
                 reuse_port: bool = False, raise_exceptions: bool = True):
        self.raise_exceptions = raise_exceptions
        self.shutdown_requested = False
        self.running = False
        self.closed = False
        self.address = None

        self.request_handler = BaseRequestHandler()
        self.selector = selectors.DefaultSelector()
        self.sock = socket.socket(family, socket.SOCK_STREAM)
        try:
            if os.name == 'posix':
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if reuse_port and sys.platform != 'win32':
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.bind(address)
            self.address = self.sock.getsockname()
            if backlog is not None:
                self.sock.listen(backlog)
            else:
                self.sock.listen()
            self.selector.register(self.sock, selectors.EVENT_READ, (ACCEPT_CONN, None))
            self.cshd_sock = socket.create_connection(self.address)
            self.sshd_sock, addr = self.sock.accept()
            self.selector.register(self.sshd_sock, selectors.EVENT_READ, (SHUTDOWN_REQUEST, None))
        except:
            self.closed = True
            self.selector.close()
            self.sock.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def set_request_handler(self, handler: BaseRequestHandler):
        self.request_handler = handler

    def select(self, timeout: Optional[float] = None):
        return self.selector.select(timeout)

    def accept(self):
        sock, addr = self.sock.accept()
        sock.setblocking(True)
        conn = ConnectionHandler(sock)
        self.selector.register(sock, selectors.EVENT_READ, (HANDLE_REQUEST, conn))

        return conn

    def close(self):
        self.closed = True
        self.selector.close()
        self.sock.close()
        self.cshd_sock.close()
        self.sshd_sock.close()

    def close_sock(self, sock: socket.socket):
        self.selector.unregister(sock)
        sock.close()

    def close_connections(self):
        for fd, key in tuple(self.selector.get_map().items()):
            reason, conn = key.data
            if reason == HANDLE_REQUEST:
                self.close_sock(conn.sock)

    def stop(self):
        if self.running and not self.shutdown_requested:
            self.shutdown_requested = True
            send(self.cshd_sock, SIGNAL_STOP)

    def shutdown(self):
        if self.running and not self.shutdown_requested:
            self.shutdown_requested = True
            send(self.cshd_sock, SIGNAL_SHUTDOWN)

    def process_socket(self, key: selectors.SelectorKey):
        reason, conn = key.data
        if reason == ACCEPT_CONN:
            self.accept()
        elif reason == HANDLE_REQUEST:
            self.handle_request(conn)

    def handle_request(self, conn: ConnectionHandler):
        try:
            data = conn.recv()
        except ConnectionError:
            self.close_sock(conn.sock)
            return
        try:
            self.request_handler.handle(conn, data)
        except ConnectionError:
            self.close_sock(conn.sock)
        except Exception as e:
            self.close_sock(conn.sock)
            logger.exception(e)
            if self.raise_exceptions:
                raise

    def handle_shutdown(self):
        signal = recv(self.sshd_sock)
        if signal == SIGNAL_SHUTDOWN:
            self.close_connections()
        elif signal == SIGNAL_STOP:
            return

    def run_once(self, timeout: Optional[float] = None):
        for key, events in self.select(timeout):
            self.process_socket(key)
            if self.shutdown_requested:
                self.handle_shutdown()
                self.shutdown_requested = False
                return True
        return False

    def run(self, poll_interval: Optional[float] = None):
        self.running = True
        try:
            while True:
                stop = self.run_once(poll_interval)
                if stop:
                    break
        finally:
            self.running = False
