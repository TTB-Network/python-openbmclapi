from dataclasses import dataclass
from enum import Enum
import os
import signal
import traceback
from .config import Config
from . import timer as Timer
from .utils import Client
from .certificate import *
from . import web
from .logger import logger

import asyncio
import ssl
from typing import Optional


class Protocol(Enum):
    HTTP = "HTTP"
    Unknown = "Unknown"
    DETECT = "Detect"

    @staticmethod
    def get(data: bytes):
        if b"HTTP/1.1" in data:
            return Protocol.HTTP
        if check_port_key == data:
            return Protocol.DETECT
        return Protocol.Unknown


@dataclass
class ProxyClient:
    proxy: "Proxy"
    origin: Client
    target: Client
    before: bytes = b""
    closed: bool = False

    def start(self):
        self._task_origin = Timer.delay(
            self.process_origin,
        )
        self._task_target = Timer.delay(
            self.process_target,
        )

    async def process_origin(self):
        try:
            self.target.write(self.before)
            while (
                (buffer := await self.origin.read(IO_BUFFER, timeout=TIMEOUT))
                and not self.origin.is_closed()
                and not self.origin.is_closed()
            ):
                self.target.write(buffer)
                self.before = b""
                await self.target.writer.drain()
        except:
            ...
        self.close()

    async def process_target(self):
        try:
            while (
                (buffer := await self.target.read(IO_BUFFER, timeout=TIMEOUT))
                and not self.target.is_closed()
                and not self.target.is_closed()
            ):
                self.origin.write(buffer)
                await self.origin.writer.drain()
        except:
            ...
        self.close()

    def close(self):
        if not self.closed:
            if not self.origin.is_closed():
                self.origin.close()
            if not self.target.is_closed():
                self.target.close()
            self.closed = True
        self.proxy.disconnect(self)


class Proxy:
    def __init__(self) -> None:
        self._tables: list[ProxyClient] = []

    async def connect(self, origin: Client, target: Client, before: bytes):
        client = ProxyClient(self, origin, target, before)
        self._tables.append(client)
        client.start()

    def disconnect(self, client: ProxyClient):
        if client not in self._tables:
            return
        self._tables.remove(client)

    def get_origin_from_ip(self, ip: tuple[str, int]):
        # ip is connected client
        for target in self._tables:
            if target.target.get_sock_address() == ip:
                return target.origin.get_address()
        return None


ssl_server: Optional[asyncio.Server] = None
server: Optional[asyncio.Server] = None
proxy: Proxy = Proxy()
restart = False
check_port_key = os.urandom(8)
PORT: int = Config.get("web.port")
TIMEOUT: int = Config.get("advanced.timeout")
SSL_PORT: int = Config.get("web.ssl_port")
PROTOCOL_HEADER_BYTES = Config.get("advanced.header_bytes")
IO_BUFFER: int = Config.get("advanced.io_buffer")


async def _handle_ssl(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    return await _handle_process(
        Client(
            reader,
            writer,
            peername=proxy.get_origin_from_ip(writer.get_extra_info("peername")),
        ),
        True,
    )


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    return await _handle_process(Client(reader, writer))


async def _handle_process(client: Client, ssl: bool = False):
    global ssl_server
    proxying = False
    try:
        while (
            header := await client.read(PROTOCOL_HEADER_BYTES, timeout=30)
        ) and not client.is_closed():
            protocol = Protocol.get(header)
            if protocol == Protocol.DETECT:
                client.write(check_port_key)
                await client.writer.drain()
                break
            if protocol == Protocol.Unknown and not ssl and ssl_server:
                target = Client(
                    *(
                        await asyncio.open_connection(
                            "127.0.0.1", ssl_server.sockets[0].getsockname()[1]
                        )
                    ),
                    peername=client.get_address(),
                )
                proxying = True
                await proxy.connect(client, target, header)
                break
            elif protocol == Protocol.HTTP:
                await web.handle(header, client)
    except (
        TimeoutError,
        asyncio.exceptions.IncompleteReadError,
        ConnectionResetError,
        OSError,
    ):
        ...
    except:
        logger.debug(traceback.format_exc())
    if not proxying and not client.is_closed():
        client.close()


async def check_ports():
    global ssl_server, server, client_side_ssl, restart, check_port_key
    while int(os.environ["ASYNCIO_STARTUP"]):
        ports: list[tuple[asyncio.Server, ssl.SSLContext | None]] = []
        for service in (
            (server, None),
            (ssl_server, client_side_ssl if get_loaded() else None),
        ):
            if not service[0]:
                continue
            ports.append((service[0], service[1]))
        closed = False
        for port in ports:
            try:
                kwargs = {}
                if port[1] is not None:
                    kwargs["ssl"] = port[1]
                    kwargs["ssl_handshake_timeout"] = 5
                if port[0] is None or not port[0].sockets:
                    closed = True
                    continue
                client = Client(
                    *(
                        await asyncio.wait_for(
                            asyncio.open_connection(
                                "127.0.0.1",
                                port[0].sockets[0].getsockname()[1],
                                **kwargs,
                            ),
                            timeout=5,
                        )
                    )
                )
                client.write(check_port_key)
                await client.writer.drain()
                key = await client.read(len(check_port_key), 5)
            except:
                logger.warn(
                    locale.t(
                        "core.warn.port_closed",
                        port=port[0].sockets[0].getsockname()[1],
                    )
                )
                logger.error(traceback.format_exc())
                closed = True
        if closed:
            restart = True
            for port in ports:
                port[0].close()
        await asyncio.sleep(5)


async def main():
    global ssl_server, server, server_side_ssl, restart
    os.environ["ASYNCIO_STARTUP"] = str(1)
    await web.init()
    certificate.load_cert(Path(".ssl/cert"), Path(".ssl/key"))
    Timer.delay(check_ports, delay=5)
    while 1:
        try:
            server = await asyncio.start_server(_handle, port=PORT)
            ssl_server = await asyncio.start_server(
                _handle_ssl,
                port=0 if SSL_PORT == PORT else SSL_PORT,
                ssl=server_side_ssl if get_loaded() else None,
            )
            logger.info(locale.t("core.info.listening", port=PORT))
            logger.info(
                locale.t(
                    "core.info.listening_ssl",
                    port=ssl_server.sockets[0].getsockname()[1],
                )
            )
            async with server, ssl_server:
                await asyncio.gather(server.serve_forever(), ssl_server.serve_forever())
        except asyncio.CancelledError:
            if not restart:
                break
            if server:
                server.close()
            if ssl_server:
                ssl_server.close()
            restart = False
        except:
            if server:
                server.close()
            if ssl_server:
                ssl_server.close()
            logger.error(traceback.format_exc())
            await asyncio.sleep(2)
    await close()
    logger.info(locale.t("core.info.shutting_down_web_service"))
    os.environ["ASYNCIO_STARTUP"] = str(0)
    os.kill(os.getpid(), signal.SIGINT)


def init():
    asyncio.run(main())


async def close():
    await web.close()


def kill(_, __):
    if int(os.environ["ASYNCIO_STARTUP"]) and server:
        server.close()
        if ssl_server:
            ssl_server.close()
        asyncio.get_running_loop().close()
        return
    exit(0)


for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, kill)
