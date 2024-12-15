import asyncio
import socket
import ssl
import time
from typing import Coroutine, Callable, Optional

ACCEPTHANDLER = Callable[[asyncio.StreamReader, asyncio.StreamWriter], Coroutine]


class TCPServer(
    asyncio.BaseProtocol
):
    def __init__(self, handle: ACCEPTHANDLER) -> None:
        self.handle = handle
        self._loop = asyncio.get_running_loop()
        self._last = time.monotonic()

    def __call__(self):
        return TCPClient(
            self, _loop=self._loop
        )

class TCPClient(
    asyncio.BaseProtocol
):
    def __init__(self, manager: TCPServer, _loop: asyncio.AbstractEventLoop) -> None:
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.manager = manager
        self._loop = asyncio.get_running_loop()
        self.handle_task: Optional[asyncio.Task] = None

    
    def connection_made(self, transport: asyncio.Transport) -> None:
        self.transport = transport
        self.reader = asyncio.StreamReader()
        self.writer = asyncio.StreamWriter(
            transport, protocol=self, reader=self.reader, loop=self._loop
        )
        self.handle_task = self._loop.create_task(self.manager.handle(self.reader, self.writer))

    async def _drain_helper(self):
        ...


    def connection_lost(self, exc: Exception | None) -> None:
        if self.writer is not None:
            self.writer.close()
            self.writer = None
        if self.handle_task is not None:
            self.handle_task.cancel()
            self.handle_task = None
        self.reader = None
        self.transport = None

    def data_received(self, data: bytes) -> None:
        if self.writer is None or self.reader is None:
            return
        self.reader.feed_data(data)

    def eof_received(self) -> bool:
        return False
    
    def __del__(self):
        if self.writer is not None:
            self.writer.close()
            self.writer = None
        if self.handle_task is not None:
            self.handle_task.cancel()
            self.handle_task = None
        self.reader = None
        self.transport = None

async def create_server(
    handle: ACCEPTHANDLER,
    host=None, port=None,
    *, family=socket.AF_UNSPEC,
    flags=socket.AI_PASSIVE, backlog=100,
    ssl=None, reuse_address=None, reuse_port=None,
    ssl_handshake_timeout=None,
    ssl_shutdown_timeout=None,
):
    server = await asyncio.get_event_loop().create_server(
        TCPServer(handle),
        host=host,
        port=port,
        family=family,
        flags=flags,
        backlog=backlog,
        ssl=ssl,
        reuse_address=reuse_address,
        reuse_port=reuse_port,
        ssl_handshake_timeout=ssl_handshake_timeout,
        ssl_shutdown_timeout=ssl_shutdown_timeout,
    )
    return server